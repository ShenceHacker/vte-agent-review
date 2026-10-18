"""Deploy a matched pilot after verified local archival of previous study data.

Run on the authorized server. Stage and verify the database while the rating
service is stopped; other server services and settings are not touched.
"""
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import time
import urllib.request

VERSION='VTE-R3-2026-10-18'
METHODS={'baseline','rag','synthesis','reviewed'}


def command(*args):return subprocess.run(args,check=True,capture_output=True,text=True).stdout.strip()
def digest(rows):return hashlib.sha256(json.dumps(rows,ensure_ascii=False).encode()).hexdigest()
def rows(path):
    with closing(sqlite3.connect(f'file:{path}?mode=ro',uri=True)) as c:
        return {name:c.execute('SELECT * FROM '+name+' ORDER BY 1,2').fetchall() for name in ('cases','outputs','ratings','accounts')}
def backup(source,target):
    with closing(sqlite3.connect(f'file:{source}?mode=ro',uri=True)) as src,closing(sqlite3.connect(target)) as dest:src.backup(dest)
    target.chmod(0o600)


def unpack(archive,target,code=False):
    with tarfile.open(archive) as tar:
        members=tar.getmembers()
        if sum(m.size for m in members)>220*1024*1024:raise ValueError('Oversized archive')
        for member in members:
            path=(target/member.name).resolve()
            allowed=member.name.startswith('vte_review/') if code else member.name in {'bundle.json','active-study.json'} or member.name.startswith('assets/')
            if not allowed or not member.isfile() or not path.is_relative_to(target):raise ValueError('Invalid archive member')
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(tar.extractfile(member).read());path.chmod(0o644 if code else 0o600)


def validate_pilot(bundle,study):
    cases=study.get('case_ids',[])
    if study.get('rubric_version')!=VERSION or len(cases)!=10 or len(set(cases))!=10:raise ValueError('Expected ten R3 pilot cases')
    if {c['id'] for c in bundle['cases']}!=set(cases) or len(bundle['cases'])!=10:raise ValueError('Cohort mismatch')
    for case in bundle['cases']:
        positions={m:[] for m in METHODS}
        for o in case['outputs']:
            if o['case_id']!=case['id']:raise ValueError('Output case mismatch')
            positions[o.get('method_id','reviewed')].append(o['position'])
        expected=list(range(case['timepoints']))
        if not expected or any(sorted(p)!=expected for p in positions.values()):raise ValueError('Incomplete paired follow-up')


def prune_to_pilot(store,case_ids):
    if not case_ids:raise ValueError('Refuse empty pilot')
    placeholders=','.join('?' for _ in case_ids);ids=tuple(case_ids)
    with store.db() as c:
        c.execute('DELETE FROM events WHERE target IN (SELECT id FROM outputs WHERE case_id NOT IN ('+placeholders+'))',ids)
        c.execute('DELETE FROM ratings WHERE output_id NOT IN (SELECT id FROM outputs WHERE case_id IN ('+placeholders+'))',ids)
        c.execute('DELETE FROM outputs WHERE case_id NOT IN ('+placeholders+')',ids)
        c.execute('DELETE FROM cases WHERE id NOT IN ('+placeholders+')',ids)
    with closing(sqlite3.connect(store.path)) as c:c.execute('VACUUM')


def deploy(code_archive,pilot_archive,archive_proof):
    import pwd
    if os.geteuid()!=0:raise RuntimeError('Run with sudo')
    base=Path('/opt/vte-review');root=Path('/var/lib/vte-review');database=root/'ratings.sqlite3';scope=root/'active-study.json'
    stamp=time.strftime('%Y%m%dT%H%M%S');release=base/'releases'/stamp
    saved=base/'backups'/('pilot-'+stamp);saved.mkdir(parents=True,mode=0o700)
    release.mkdir(parents=True);unpack(code_archive,release,True)
    incoming=saved/'incoming';incoming.mkdir();unpack(pilot_archive,incoming)
    bundle=json.loads((incoming/'bundle.json').read_text());study=json.loads((incoming/'active-study.json').read_text())
    validate_pilot(bundle,study)
    for path in (incoming/'assets').glob('*'):
        if hashlib.sha256(path.read_bytes()).hexdigest()+'.png'!=path.name:raise ValueError('Asset digest mismatch')
    required=set()
    for case in bundle['cases']:
        for item in [case.get('baseline',{}),*case['outputs']]:
            required.update(a['id'] for a in item.get('images',[]))
            required.update(a['id'] for a in item.get('reference',{}).get('images',[]))
    if required!={p.name for p in (incoming/'assets').glob('*')}:raise ValueError('Asset inventory mismatch')
    proof=json.loads(Path(archive_proof).read_text())
    if proof.get('verified') is not True or not proof.get('archive_sha256') or not proof.get('local_archive'):
        raise RuntimeError('Verified local archive proof is required before removing older study data')
    previous=(base/'current').resolve();old_scope=scope.read_bytes() if scope.exists() else None
    account=pwd.getpwnam('vte-review');switched=False
    command('systemctl','stop','vte-review.service')
    try:
        before=rows(database);backup(database,saved/'ratings.sqlite3')
        for name,old in before.items():
            if proof['live_snapshot'][name]!={'rows':len(old),'sha256':digest(old)}:
                raise RuntimeError('Server study data changed after local archive verification; archive again')
        if old_scope is not None:(saved/'active-study.json').write_bytes(old_scope)
        staged=saved/'stage';staged.mkdir();backup(database,staged/'ratings.sqlite3')
        (staged/'active-study.json').write_bytes((incoming/'active-study.json').read_bytes())
        sys.path.insert(0,str(release))
        from vte_review.rating_portal import Store
        store=Store(staged,[],'deployment-validation-only-'*3);store.import_bundle(bundle)
        after=rows(staged/'ratings.sqlite3')
        for name,old in before.items():
            if not set(old)<=set(after[name]):raise RuntimeError('Existing '+name+' changed')
        # Only a verified archive authorizes physical removal. Accounts remain
        # available; pilot ratings, if any, are never removed or re-versioned.
        prune_to_pilot(store,study['case_ids'])
        after=rows(staged/'ratings.sqlite3')
        if before['accounts']!=after['accounts']:raise RuntimeError('Doctor accounts changed')
        if len(after['cases'])!=10 or len(after['outputs'])!=4*sum(c['timepoints'] for c in bundle['cases']):raise RuntimeError('Unexpected pilot database size')
        methods=store.list_methods('deployment-validation')
        expected=sum(c['timepoints'] for c in bundle['cases'])
        if any(m['total']!=expected or m['cases']!=10 for m in methods):raise RuntimeError('Pilot visibility mismatch')
        with closing(sqlite3.connect(staged/'ratings.sqlite3')) as c:
            if c.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise RuntimeError('Database integrity check failed')
        for path in (incoming/'assets').glob('*'):
            target=root/'assets'/path.name
            if target.exists() and target.read_bytes()!=path.read_bytes():raise RuntimeError('Existing asset changed')
            if not target.exists():shutil.copyfile(path,target);target.chmod(0o640);os.chown(target,account.pw_uid,account.pw_gid)
        next_db=root/'ratings-next.sqlite3';shutil.copyfile(staged/'ratings.sqlite3',next_db);next_db.chmod(0o600);os.chown(next_db,account.pw_uid,account.pw_gid)
        next_db.replace(database)
        scope.write_bytes((incoming/'active-study.json').read_bytes());scope.chmod(0o640);os.chown(scope,account.pw_uid,account.pw_gid)
        temporary=base/('next-'+stamp);temporary.symlink_to(release);temporary.replace(base/'current');switched=True
        command('systemctl','start','vte-review.service')
        for _ in range(15):
            try:
                req=urllib.request.Request('http://127.0.0.1:8792/vte-review/api/health',headers={'Host':'api.forceeasyai.com'})
                with urllib.request.urlopen(req,timeout=3) as response:health=json.load(response)
                if health=={'status':'ok','rubric_version':VERSION}:break
            except (OSError,ValueError):pass
            time.sleep(1)
        else:raise RuntimeError('Pilot health check failed')
        result={'release':str(release),'previous_release':str(previous),'backup':str(saved),'health':health,'pilot_cases':study['case_ids'],'methods':methods,
                'archived_locally':{t:{'rows':len(r),'sha256':digest(r)} for t,r in before.items()},'local_archive_sha256':proof['archive_sha256'],'database_totals':{t:len(r) for t,r in after.items()},'quick_check':'ok'}
        (saved/'deployment.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
    except Exception:
        command('systemctl','stop','vte-review.service')
        if switched:
            backup(database,saved/'rollback-recovery.sqlite3')
            restore=base/('restore-'+stamp);restore.symlink_to(previous);restore.replace(base/'current')
        if (saved/'ratings.sqlite3').exists():
            shutil.copyfile(saved/'ratings.sqlite3',database);os.chown(database,account.pw_uid,account.pw_gid)
        if old_scope is None:scope.unlink(missing_ok=True)
        else:scope.write_bytes(old_scope)
        command('systemctl','start','vte-review.service');raise


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('code',type=Path);parser.add_argument('pilot',type=Path);parser.add_argument('--archive-proof',type=Path,required=True)
    args=parser.parse_args();deploy(args.code,args.pilot,args.archive_proof)
