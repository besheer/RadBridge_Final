"""Scheduled RadBridge backup worker.

Backs up configured reports, attachments and PostgreSQL dumps through rclone.
PACS binary storage is intentionally excluded unless PACS_STORAGE_PATH is
explicitly mounted/configured. See docs/STORAGE_BACKUP.md before changing this.
"""

import os,time,subprocess,datetime,shlex
from pathlib import Path
from urllib.parse import urlparse
from app import app,db,CloudBackupConfig,BackupRun,REPORT_DIR,ATTACHMENT_DIR

def run(cmd):
    p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    if p.returncode!=0:raise RuntimeError(p.stderr[-2000:])
    return p.stdout

def db_dump(outdir):
    url=urlparse(os.environ.get("DATABASE_URL",""))
    path=Path(outdir);path.mkdir(parents=True,exist_ok=True)
    target=path/("ris-"+datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")+".dump")
    env=os.environ.copy()
    if url.password:env["PGPASSWORD"]=url.password
    cmd=["pg_dump","-Fc","-h",url.hostname or "ris-db","-p",str(url.port or 5432),"-U",url.username or "risweb","-d",(url.path or "/risweb").lstrip("/"),"-f",str(target)]
    p=subprocess.run(cmd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    if p.returncode!=0:raise RuntimeError(p.stderr[-2000:])
    return str(target)

def sync_folder(remote,root,local,name):
    if not remote:return
    run(["rclone","copy",local,f"{remote}:{root.rstrip('/')}/{name}","--checksum","--create-empty-src-dirs"])

with app.app_context():
    while True:
        now=datetime.datetime.now()
        for cfg in CloudBackupConfig.query.filter_by(active=True).all():
            last=BackupRun.query.filter_by(config_id=cfg.id,status="SUCCESS").order_by(BackupRun.id.desc()).first()
            if now.hour!=int(cfg.schedule_hour or 2):continue
            if last and last.started_at.date()==now.date():continue
            row=BackupRun(config_id=cfg.id,status="RUNNING");db.session.add(row);db.session.commit()
            try:
                if cfg.include_reports:sync_folder(cfg.rclone_remote,cfg.remote_root,REPORT_DIR,"reports")
                if cfg.include_attachments:sync_folder(cfg.rclone_remote,cfg.remote_root,ATTACHMENT_DIR,"attachments")
                if cfg.include_database:
                    row.database_file=db_dump(os.getenv("BACKUP_DIR","/app/backups"))
                    sync_folder(cfg.rclone_remote,cfg.remote_root,str(Path(row.database_file).parent),"database")
                # PACS image backup is deliberately not copied by this worker unless a mounted PACS path is explicitly configured.
                if cfg.include_pacs and os.getenv("PACS_STORAGE_PATH"):
                    sync_folder(cfg.rclone_remote,cfg.remote_root,os.getenv("PACS_STORAGE_PATH"),"pacs-archive")
                row.status="SUCCESS";row.completed_at=datetime.datetime.utcnow()
            except Exception as exc:
                row.status="FAILED";row.last_error=str(exc)[:4000];row.completed_at=datetime.datetime.utcnow()
            db.session.commit()
        time.sleep(300)
