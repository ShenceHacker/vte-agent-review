"""Code-only R2 replacement on the existing authorized FE installation.

Refuse if any physician input appeared since preflight. Empty R1 auto-drafts
may be reset after a backup; never discard physician work.
No changes to cases, output hashes, assets, mail configuration or Nginx.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tarfile
import time
import urllib.request


def command(*args):
    return subprocess.run(args,check=True,text=True,capture_output=True).stdout.strip()


def snapshot(database):
    with sqlite3.connect(f'file:{database}?mode=ro',uri=True) as c:
        rows=c.execute('SELECT id,content_hash FROM outputs ORDER BY id').fetchall()
        return {'cases':c.execute('SELECT COUNT(*) FROM cases').fetchone()[0],
                'outputs':len(rows),'output_hashes_sha256':hashlib.sha256(json.dumps(rows).encode()).hexdigest(),
                'ratings':c.execute('SELECT COUNT(*) FROM ratings').fetchone()[0]}


def check_unrated(database):
    with sqlite3.connect(f'file:{database}?mode=ro',uri=True) as c:
        for version,status,raw in c.execute('SELECT rubric_version,status,payload FROM ratings'):
            p=json.loads(raw)
            if version!='VTE-R1-2026-10-12' or status!='draft' or set(p)-{'scores','error_types','active_seconds'} or p.get('scores') or p.get('error_types'):
                raise RuntimeError('Physician input now exists: stop and inspect; do not erase or relabel it')


def deploy(archive,preserve_ratings=False):
    if os.geteuid()!=0:raise RuntimeError('Run with sudo')
    base=Path('/opt/vte-review');current=base/'current'
    database=Path('/var/lib/vte-review/ratings.sqlite3')
    previous=current.resolve(strict=True)
    before=snapshot(database)
    if not preserve_ratings:check_unrated(database)
    stamp=time.strftime('%Y%m%dT%H%M%S')
    release=base/'releases'/stamp;release.mkdir(parents=True,exist_ok=False)
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            target=(release/member.name).resolve()
            if not target.is_relative_to(release) or not member.isfile() or not member.name.startswith('vte_review/'):raise ValueError('Invalid code release member')
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(tar.extractfile(member).read());target.chmod(0o644)
    backup=base/'backups'/('r2-'+stamp);backup.mkdir(parents=True,mode=0o700)
    command('systemctl','stop','vte-review.service')
    switched=False
    try:
        before=snapshot(database)
        if not preserve_ratings:check_unrated(database)
        else:
            with sqlite3.connect(f'file:{database}?mode=ro',uri=True) as c:
                if c.execute("SELECT COUNT(*) FROM ratings WHERE rubric_version!='VTE-R2-2026-10-13'").fetchone()[0]:raise RuntimeError('Incompatible rubric version; code-only update cannot migrate ratings')
        with sqlite3.connect(f'file:{database}?mode=ro',uri=True) as source,sqlite3.connect(backup/'ratings.sqlite3') as dest:source.backup(dest)
        (backup/'ratings.sqlite3').chmod(0o600)
        temporary=base/('next-'+stamp);temporary.symlink_to(release);temporary.replace(current);switched=True
        command('systemctl','start','vte-review.service')
        for _ in range(15):
            try:
                request=urllib.request.Request('http://127.0.0.1:8792/vte-review/api/health',headers={'Host':'api.forceeasyai.com'})
                with urllib.request.urlopen(request,timeout=3) as response:health=json.load(response)
                if health=={'status':'ok','rubric_version':'VTE-R2-2026-10-13'}:break
            except (OSError,ValueError):pass
            time.sleep(1)
        else:raise RuntimeError('R2 health check failed')
        after=snapshot(database)
        if any(before[k]!=after[k] for k in ('cases','outputs','output_hashes_sha256')):raise RuntimeError('Immutable case/output verification failed')
        if not preserve_ratings:
            # R1 tabs are rejected by R2 before save. Reset only still-empty R1
            # auto-drafts; newly started R2 reviews are never touched.
            with sqlite3.connect(database) as c:
                c.execute('BEGIN IMMEDIATE')
                for email,oid,status,raw in c.execute("SELECT email,output_id,status,payload FROM ratings WHERE rubric_version='VTE-R1-2026-10-12'").fetchall():
                    p=json.loads(raw)
                    if status!='draft' or set(p)-{'scores','error_types','active_seconds'} or p.get('scores') or p.get('error_types'):raise RuntimeError('Unexpected physician input; no migration applied')
                    c.execute("UPDATE ratings SET rubric_version='VTE-R2-2026-10-13',payload='{}',revision=0,opened_at=?,updated_at=? WHERE email=? AND output_id=?",(time.time(),time.time(),email,oid))
        result={'release':str(release),'previous_release':str(previous),'backup':str(backup),'health':health,'before':before,'after':after,'service':command('systemctl','is-active','vte-review.service')}
        (backup/'deployment.json').write_text(json.dumps(result,indent=2));(backup/'deployment.json').chmod(0o600)
        print(json.dumps(result))
    except Exception:
        if switched:
            command('systemctl','stop','vte-review.service')
            restore=base/('restore-'+stamp);restore.symlink_to(previous);restore.replace(current)
        command('systemctl','start','vte-review.service')
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('archive',type=Path);parser.add_argument('--preserve-ratings',action='store_true',help='R2 code-only update; never modify rating rows')
    args=parser.parse_args();deploy(args.archive,args.preserve_ratings)
