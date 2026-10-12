"""Run on the authorized FE host after uploading the reviewed release archive."""
from pathlib import Path
import argparse,grp,json,os,pwd,secrets,shutil,smtplib,ssl,sqlite3,subprocess,tarfile,time,urllib.request

def cmd(*args,**kw):return subprocess.run(args,check=True,text=True,capture_output=True,**kw).stdout.strip()
def write(path,text,mode=0o640):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text);path.chmod(mode)

def deploy(archive,reviewers):
    if os.geteuid()!=0:raise RuntimeError('Run with sudo')
    base=Path('/opt/vte-review');data=Path('/var/lib/vte-review');config=Path('/etc/vte-review')
    backup=Path('/home/ubuntu/vte-review-deploy-20261012');backup.mkdir(exist_ok=True);backup.chmod(0o700)
    try:pwd.getpwnam('vte-review')
    except KeyError:cmd('useradd','--system','--home-dir',str(data),'--shell','/usr/sbin/nologin','vte-review')
    user=pwd.getpwnam('vte-review');gid=user.pw_gid
    release=base/'releases'/time.strftime('%Y%m%dT%H%M%S');release.mkdir(parents=True,exist_ok=False)
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            target=(release/member.name).resolve()
            if not target.is_relative_to(release.resolve()) or not member.isfile() or not member.name.startswith(('vte_review/','bundle/')):raise ValueError('Unsafe release member')
        for member in tar.getmembers():
            target=release/member.name;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(tar.extractfile(member).read());target.chmod(0o644)
    for file in [release/'bundle',*(release/'bundle').rglob('*')]:
        os.chown(file,0,gid);file.chmod(0o750 if file.is_dir() else 0o640)
    for path in (data,config):path.mkdir(parents=True,exist_ok=True);os.chown(path,0,gid);path.chmod(0o750)
    os.chown(data,user.pw_uid,gid)
    # Read the already configured FE mail sender entirely on this host. Never print credentials.
    code='import app,json\nwith app.db() as c: print(json.dumps(app.smtp_config(c)))'
    mail=json.loads(cmd('docker','exec','fe-shop-api','python','-c',code))
    if not mail:raise RuntimeError('FE SMTP configuration unavailable')
    context=ssl.create_default_context()
    with smtplib.SMTP_SSL(mail['host'],int(mail['port']),context=context,timeout=20) as smtp:smtp.login(mail['username'],mail['password'])
    mail_path=config/'smtp.json';write(mail_path,json.dumps(mail));os.chown(mail_path,0,gid)
    env_path=config/'service.env'
    if not env_path.exists():
        if not reviewers or any('\n' in e or '@' not in e for e in reviewers):raise ValueError('An explicit reviewer allowlist is required')
        write(env_path,'VTE_PORTAL_SECRET='+secrets.token_urlsafe(48)+'\nVTE_REVIEWERS='+','.join(reviewers)+'\nVTE_SMTP_CONFIG=/etc/vte-review/smtp.json\n',0o600)
    values=dict(line.split('=',1) for line in env_path.read_text().splitlines() if '=' in line)
    if (data/'ratings.sqlite3').exists():
        before_db=backup/('ratings-before-'+time.strftime('%Y%m%dT%H%M%S')+'.sqlite3')
        with sqlite3.connect(data/'ratings.sqlite3') as a,sqlite3.connect(before_db) as b:a.backup(b)
        before_db.chmod(0o600)
    # Import immutable reports into the existing rating database; preserve all physician scores.
    assets=data/'assets';assets.mkdir(exist_ok=True)
    for file in (release/'bundle/assets').glob('*.png'):shutil.copyfile(file,assets/file.name)
    shutil.copyfile(release/'bundle/bundle.json',data/'bundle.json')
    for file in data.rglob('*'):
        os.chown(file,user.pw_uid,gid);file.chmod(0o750 if file.is_dir() else 0o640)
    cmd('/usr/bin/python3','-m','vte_review.rating_portal','--root',str(data),'--import-bundle',str(data/'bundle.json'),'--import-only',cwd=release,env={**os.environ,**values})
    for file in data.iterdir():os.chown(file,user.pw_uid,gid)
    current=base/'current';previous=os.readlink(current) if current.is_symlink() else None
    temporary=base/'next';temporary.symlink_to(release);temporary.replace(current)
    unit='''[Unit]
Description=FE VTE Physician Review Portal
After=network-online.target
[Service]
Type=simple
User=vte-review
Group=vte-review
WorkingDirectory=/opt/vte-review/current
EnvironmentFile=/etc/vte-review/service.env
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/python3 -m vte_review.rating_portal --root /var/lib/vte-review --port 8792 --origin https://api.forceeasyai.com --prefix /vte-review
Restart=on-failure
RestartSec=3
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/vte-review
[Install]
WantedBy=multi-user.target
'''
    write(Path('/etc/systemd/system/vte-review.service'),unit,0o644)
    cmd('systemctl','daemon-reload');cmd('systemctl','enable','--now','vte-review.service');cmd('systemctl','restart','vte-review.service')
    for attempt in range(15):
        try:
            req=urllib.request.Request('http://127.0.0.1:8792/vte-review/api/health',headers={'Host':'api.forceeasyai.com'})
            if json.load(urllib.request.urlopen(req,timeout=3))['status']=='ok':break
        except Exception:time.sleep(1)
    else:raise RuntimeError('Portal did not start')
    nginx=Path('/etc/nginx/sites-enabled/api.forceeasyai.com').resolve();before=nginx.read_text()
    if '# BEGIN VTE REVIEW' not in before:
        (backup/'nginx.before').write_text(before);(backup/'nginx.before').chmod(0o600)
        block='''    # BEGIN VTE REVIEW
    location = /vte-review { return 302 /vte-review/; }
    location ^~ /vte-review/ {
        proxy_pass http://127.0.0.1:8792;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_read_timeout 35s;
        client_max_body_size 64k;
        add_header Cache-Control "no-store" always;
    }
    # END VTE REVIEW

'''
        marker='    location ^~ /shot-api/ {'
        if before.count(marker)!=1:raise RuntimeError('Nginx insertion anchor is not unique')
        nginx.write_text(before.replace(marker,block+marker))
        try:cmd('nginx','-t');cmd('systemctl','reload','nginx')
        except Exception:nginx.write_text(before);cmd('nginx','-t');cmd('systemctl','reload','nginx');raise
    result={'url':'https://api.forceeasyai.com/vte-review/','release':str(release),'previous_release':previous,'smtp_authentication':'passed; no test mail sent','reviewer_count':len(values['VTE_REVIEWERS'].split(',')),'service':cmd('systemctl','is-active','vte-review.service')}
    write(backup/'deployment.json',json.dumps(result,indent=2),0o600);print(json.dumps(result))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('archive',type=Path);p.add_argument('--reviewer',action='append',default=[]);a=p.parse_args();deploy(a.archive,a.reviewer)
