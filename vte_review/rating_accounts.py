"""Provision explicitly requested reviewer accounts; read password only on stdin.

Run on the portal host with access to its protected environment file. Never
place the password in command-line arguments, source, logs or configuration.
"""
import argparse
import hashlib
import hmac
import json
from pathlib import Path
import sys
from .rating_portal import Store,USERNAME,PASSWORD_ITERATIONS


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--user',action='append',required=True)
    args=parser.parse_args()
    if len(set(args.user))!=len(args.user) or any(not USERNAME.fullmatch(u) for u in args.user):raise ValueError('Invalid or duplicate usernames')
    password=sys.stdin.readline().rstrip('\r\n')
    if not 6<=len(password)<=256:raise ValueError('A 6–256 character password is required on stdin')
    values=dict(line.split('=',1) for line in args.config.read_text().splitlines() if '=' in line)
    store=Store(args.root,values.get('VTE_REVIEWERS','').split(','),values['VTE_PORTAL_SECRET'])
    pending=[]
    with store.db() as c:
        for username in args.user:
            row=c.execute('SELECT * FROM accounts WHERE username=?',(username,)).fetchone()
            if not row:pending.append(username);continue
            digest=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(row['salt']),PASSWORD_ITERATIONS).hex()
            if not row['enabled'] or not hmac.compare_digest(digest,row['password_hash']):raise ValueError('Existing account differs; no account has been changed')
    for username in pending:store.create_account(username,password)
    print(json.dumps({'accounts':args.user,'created':len(pending)}))


if __name__=='__main__':main()
