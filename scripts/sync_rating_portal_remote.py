"""Import a data-only portal update on FE; do not replace the rating database."""
from pathlib import Path
import sys,tarfile,json,os,sqlite3,time
ROOT=Path('/opt/vte-review/current');sys.path.insert(0,str(ROOT))
from vte_review.rating_portal import Store

def sync(archive):
    root=Path('/var/lib/vte-review');config=Path('/etc/vte-review/service.env')
    env=dict(line.split('=',1) for line in config.read_text().splitlines() if '=' in line)
    with tarfile.open(archive) as t:
        if sum(m.size for m in t.getmembers())>200*1024*1024:raise ValueError('Update too large')
        for m in t.getmembers():
            if not m.isfile() or not (m.name=='bundle.json' or m.name.startswith('assets/') and len(Path(m.name).parts)==2 and Path(m.name).name.endswith('.png')):raise ValueError('Invalid update member')
            path=(root/m.name).resolve()
            if not path.is_relative_to(root.resolve()):raise ValueError('Unsafe update path')
        bundle=json.load(t.extractfile('bundle.json'))
        for m in t.getmembers():
            if m.name.startswith('assets/'):
                raw=t.extractfile(m).read()
                import hashlib
                if not raw.startswith(b'\x89PNG') or Path(m.name).name!=hashlib.sha256(raw).hexdigest()+'.png':raise ValueError('Asset hash mismatch')
                dest=root/m.name;dest.write_bytes(raw);dest.chmod(0o640)
                import pwd
                user=pwd.getpwnam('vte-review');os.chown(dest,user.pw_uid,user.pw_gid)
    backup=Path('/home/ubuntu/vte-review-deploy-20261012')/('ratings-sync-'+time.strftime('%Y%m%dT%H%M%S')+'.sqlite3')
    with sqlite3.connect(root/'ratings.sqlite3') as a,sqlite3.connect(backup) as b:a.backup(b)
    backup.chmod(0o600)
    store=Store(root,env['VTE_REVIEWERS'].split(','),env['VTE_PORTAL_SECRET']);store.import_bundle(bundle)
    result={'cases':len(bundle['cases']),'outputs':sum(len(c['outputs']) for c in bundle['cases']),'at':time.time()}
    (root/'last-import.json').write_text(json.dumps(result));print(json.dumps(result))

if __name__=='__main__':sync(Path(sys.argv[1]))
