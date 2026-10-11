"""Runtime-bound application.components.operations; dependencies are supplied at composition.

Legacy behavior is preserved; new policies belong in the independent domain layer.
"""

def install_0002(_rb):
    def qa_n8n_call(url,payload=None,timeout=15):
        if not url:
            return None,'N8N_WEBHOOK_NOT_CONFIGURED'

        try:
            r=_rb.requests.post(
                url,
                json=payload or {},
                timeout=timeout
            )

            if r.status_code >= 400:
                return None,'N8N_HTTP_%s:%s' % (
                    r.status_code,
                    (r.text or '')[:500]
                )

            try:
                return r.json(),None
            except Exception:
                return {'raw':(r.text or '')[:2000]},None

        except Exception as exc:
            return None,str(exc)
    return qa_n8n_call


def install_0003(_rb):
    def qa_run_summary(row):
        return {
            'id':row.id,
            'run_type':row.run_type,
            'status':row.status,
            'release_name':row.release_name,
            'environment':row.environment,
            'total_tests':int(row.total_tests or 0),
            'passed_tests':int(row.passed_tests or 0),
            'failed_tests':int(row.failed_tests or 0),
            'critical_tests':int(row.critical_tests or 0),
            'warning_tests':int(row.warning_tests or 0),
            'external_execution_id':row.external_execution_id or '',
            'started_at':row.started_at.isoformat() if row.started_at else None,
            'finished_at':row.finished_at.isoformat() if row.finished_at else None,
        }
    return qa_run_summary


def install_0055(_rb):
    def storage_defaults():
        defaults=[
          ('REPORTS','Reports',_rb.REPORT_DIR,'LOCAL'),
          ('ATTACHMENTS','Attachments',_rb.ATTACHMENT_DIR,'LOCAL'),
          ('EXPORTS','Exports',_rb.os.getenv('EXPORT_DIR','/app/exports'),'LOCAL'),
          ('BACKUPS','Backups',_rb.os.getenv('BACKUP_DIR','/app/backups'),'BACKUP'),
          ('PACS','PACS DICOM Storage',_rb.os.getenv('PACS_STORAGE_PATH','/var/lib/orthanc/db'),'PACS')]
        for code,label,path,typ in defaults:
            if not _rb.StorageLocation.query.filter_by(code=code).first():
                _rb.db.session.add(_rb.StorageLocation(code=code,label=label,path=path,storage_type=typ))
        _rb.db.session.commit()
    return storage_defaults


def install_0278(_rb):
    def admin_storage_paths():
        candidates={
            'Reports':_rb.os.getenv('REPORTS_DIR') or _rb.os.getenv('REPORT_DIR') or '/app/reports',
            'Attachments':_rb.os.getenv('ATTACHMENTS_DIR') or _rb.os.getenv('ATTACHMENT_DIR') or '/app/attachments',
            'Uploads':_rb.os.getenv('UPLOAD_DIR') or '/app/uploads',
            'Word / Generated Documents':_rb.os.getenv('WORD_REPORTS_DIR') or _rb.os.getenv('WORD_DIR') or '/app/reports',
            'OCR':_rb.os.getenv('OCR_DIR') or '/app/uploads',
            'Backups':_rb.os.getenv('RIS_BACKUP_DIR') or _rb.os.getenv('BACKUP_DIR') or '/app/backups',
        }
        rows=[]
        for label,path in candidates.items():
            path=_rb.os.path.abspath(path)
            exists=_rb.os.path.exists(path)
            writable=_rb.os.access(path,_rb.os.W_OK) if exists else _rb.os.access(_rb.os.path.dirname(path) or '/',_rb.os.W_OK)
            size=0
            if exists:
                try:
                    for root,dirs,files in _rb.os.walk(path):
                        for f in files:
                            try:size+=_rb.os.path.getsize(_rb.os.path.join(root,f))
                            except OSError:pass
                except Exception:pass
            rows.append({'label':label,'path':path,'exists':exists,'writable':writable,'size':size})
        return rows
    return admin_storage_paths


def install_0282(_rb):
    def admin_backup_dir(create=True):
        path=_rb.os.path.abspath(
            _rb.os.getenv('RIS_BACKUP_DIR')
            or _rb.os.getenv('BACKUP_DIR')
            or '/app/backups'
        )
        if create:
            _rb.os.makedirs(path,exist_ok=True)
        return path
    return admin_backup_dir


def install_0508(_rb):
    def _rb_db_health():
        try:
            value = _rb.db.session.execute(
                _rb.text('SELECT 1')
            ).scalar()

            return {
                'status':
                    'HEALTHY'
                    if value == 1
                    else 'DEGRADED',
                'detail': str(value),
            }

        except Exception as exc:

            try:
                _rb.db.session.rollback()
            except Exception:
                pass

            return {
                'status': 'FAILED',
                'detail': type(exc).__name__,
            }
    return _rb_db_health


def install_0827(_rb):
    def resolve_storage_target(storage_type='PACS', branch_id=None, company_code='', role='PRIMARY'):
        """Resolve the preferred active storage target for a workload.

    Precedence: exact branch/company scope, branch scope, company scope, then
    global. Lower numeric priority wins. This resolver only selects metadata;
    the OS/container must already expose the mount and Orthanc must be pointed
    to the selected PACS mount during a controlled deployment/migration.
    """
        typ=str(storage_type or 'PACS').upper(); role=str(role or 'PRIMARY').upper(); company=str(company_code or '').upper().strip()
        rows=_rb.StorageLocation.query.filter_by(active=True,storage_type=typ,role=role).all()
        def rank(x):
            scope=9
            if branch_id and x.branch_id==branch_id and company and (x.company_code or '').upper()==company: scope=0
            elif branch_id and x.branch_id==branch_id and not x.company_code: scope=1
            elif company and not x.branch_id and (x.company_code or '').upper()==company: scope=2
            elif not x.branch_id and not x.company_code: scope=3
            return (scope,int(x.priority or 100),x.id)
        candidates=[x for x in rows if rank(x)[0]<9]
        return sorted(candidates,key=rank)[0] if candidates else None
    return resolve_storage_target


def install_0828(_rb):
    def refresh_storage_health(row):
        """Refresh capacity/writability for a mounted target without changing data."""
        try:
            if not row.path or not _rb.os.path.exists(row.path):
                row.health_status='OFFLINE';row.last_health_at=_rb.datetime.utcnow();return row
            usage=_rb.shutil.disk_usage(row.path)
            row.capacity_bytes=int(usage.total);row.free_bytes=int(usage.free)
            writable=_rb.os.access(row.path,_rb.os.W_OK)
            row.health_status='READ_ONLY' if (row.read_only or not writable) else 'HEALTHY'
        except Exception as exc:
            row.health_status='ERROR';row.notes=((row.notes or '')+'\nHealth: '+str(exc))[-4000:]
        row.last_health_at=_rb.datetime.utcnow();return row
    return refresh_storage_health

