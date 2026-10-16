"""Redacted source/history checks for accidental secrets and operational data.

Heuristic guard only: it cannot certify absence of PHI or every credential format.
No findings include matched secret bytes. No application/database/provider is loaded.
"""
import argparse
import json
from pathlib import Path, PurePosixPath
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
RULES={
    'private-key':re.compile(rb'-{5}BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-{5}\r?\n[A-Za-z0-9+/=\r\n]{32,}'),
    'github-token':re.compile(rb'\b(?:gh[pousr]_[A-Za-z0-9_]{30,}|github_pat_[A-Za-z0-9_]{40,})\b'),
    'aws-access-key':re.compile(rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    'slack-token':re.compile(rb'\bxox[baprs]-[A-Za-z0-9-]{25,}\b'),
    'stripe-live-secret':re.compile(rb'\bsk_live_[A-Za-z0-9]{20,}\b'),
}


def forbidden_path(path):
    parts=PurePosixPath(path).parts;name=parts[-1].lower()
    if name.endswith('.example'):return False
    if name=='.env' or name.startswith('.env.') or name.endswith('.env'):return True
    if name in {'id_rsa','id_ed25519','id_dsa','id_ecdsa'}:return True
    if PurePosixPath(name).suffix in {'.pem','.key','.p12','.pfx','.jks','.db','.sqlite','.sqlite3','.dump','.dcm','.dicom'}:return True
    return any(part.lower() in {'secrets','report-files','attachments','backups','test-runtime'} for part in parts)


def inspect_bytes(path, data):
    issues=[{'path':path,'rule':'operational-or-secret-path','line':None}] if forbidden_path(path) else []
    for rule,pattern in RULES.items():
        for match in pattern.finditer(data):
            issues.append({'path':path,'rule':rule,'line':data.count(b'\n',0,match.start())+1})
    return issues


def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)


def current_findings():
    paths=[item.decode('utf-8') for item in git('ls-files','-z').split(b'\0') if item]
    issues=[]
    for path in paths:
        target=ROOT/path
        if target.is_symlink():
            issues.append({'path':path,'rule':'symlink-requires-manual-review','line':None});continue
        if not target.resolve().is_relative_to(ROOT):
            issues.append({'path':path,'rule':'path-outside-source-root','line':None});continue
        issues.extend(inspect_bytes(path,target.read_bytes()))
    return paths,issues


def history_findings():
    objects={}
    for raw in git('rev-list','--objects','--all').decode('utf-8').splitlines():
        oid,_,path=raw.partition(' ');objects[oid]=path
    checks=git('cat-file','--batch-check=%(objectname) %(objecttype) %(objectsize)',
               '--batch-all-objects').decode('utf-8').splitlines()
    blobs=[line.split()[0] for line in checks if line.split()[1]=='blob' and line.split()[0] in objects]
    issues=[]
    process=subprocess.Popen(['git','cat-file','--batch'],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    try:
        for oid in blobs:
            process.stdin.write((oid+'\n').encode('ascii'));process.stdin.flush()
            header=process.stdout.readline().decode('ascii').split()
            if len(header)!=3 or header[1]!='blob':raise RuntimeError('Unexpected Git blob response')
            size=int(header[2]);data=process.stdout.read(size)
            if len(data)!=size or process.stdout.read(1)!=b'\n':raise RuntimeError('Truncated Git blob response')
            for issue in inspect_bytes(objects[oid] or '(unmapped blob)',data):
                issues.append(dict(issue,blob=oid))
        process.stdin.close()
        if process.wait()!=0:raise RuntimeError('History scan failed')
    finally:
        if process.poll() is None:process.kill();process.wait()
    return len(blobs),issues


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history',action='store_true',help='Also inspect reachable local Git blobs')
    parser.add_argument('--output',type=Path,help='Optional report containing rule/location only')
    args=parser.parse_args();paths,issues=current_findings();blobs=0
    if args.history:
        blobs,history=history_findings();issues.extend(history)
    report=dict(tracked_files=len(paths),history_blobs=blobs,issues=issues,
        limits='Heuristic secret/path checks; does not certify all credentials, PHI, assets or server security.')
    if args.output:args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))
    return int(bool(issues))


if __name__=='__main__':raise SystemExit(main())
