"""Run tests only against synthetic isolated databases and temporary file storage."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]

def checked_pg_url(value):
    url=urlsplit(value)
    if url.scheme!="postgresql+psycopg2" or url.hostname not in {"localhost","127.0.0.1","postgres"} or url.path!="/radbridge_dev_test" or url.username!="radbridge_test":
        raise ValueError("Only the dedicated local radbridge_dev_test database/user is allowed")
    return value

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--postgres",action="store_true",help="Only isolated RT/readiness PostgreSQL contracts; may reset this synthetic test DB")
    parser.add_argument("--postgres-suite", choices=("clinical", "assignment", "scope", "reporting", "finance", "inventory", "registration"), default="clinical")
    parser.add_argument("targets",nargs="*")
    args=parser.parse_args()
    if args.postgres and args.targets:parser.error("PostgreSQL mode has a fixed scoped suite")
    if not args.postgres and args.postgres_suite != "clinical":parser.error("--postgres-suite requires --postgres")
    with tempfile.TemporaryDirectory(prefix="radbridge-test-") as tmp:
        tmp=Path(tmp)
        env=dict(os.environ,SECRET_KEY="SYNTHETIC-TEST-ONLY",RADBRIDGE_BOOTSTRAP_ON_IMPORT="0",REPORT_DIR=str(tmp/"reports"),ATTACHMENT_DIR=str(tmp/"attachments"),BACKUP_DIR=str(tmp/"backups"),PYTHONUTF8="1",
                 ORTHANC_URL="http://127.0.0.1:9",PACS_ORTHANC_URL="http://127.0.0.1:9")
        if args.postgres:
            try:dsn=checked_pg_url(os.environ.get("RADBRIDGE_TEST_DATABASE_URL",""))
            except ValueError as e:parser.error(str(e))
            source=tmp/"ris"
            shutil.copytree(ROOT/"ris",source,ignore=shutil.ignore_patterns("__pycache__",".pytest_cache",".venv"))
            fixture=source/"tests/conftest.py"
            content=fixture.read_text(encoding="utf-8-sig")
            first='os.environ["DATABASE_URL"] = "sqlite:///:memory:"'
            second='SQLALCHEMY_DATABASE_URI="sqlite:///:memory:"'
            if content.count(first)!=1 or content.count(second)!=1:raise RuntimeError("Fixture contract changed; review PG adaptation")
            content=content.replace(first,'os.environ["DATABASE_URL"] = os.environ["RADBRIDGE_TEST_DATABASE_URL"]')
            content=content.replace(second,'SQLALCHEMY_DATABASE_URI=os.environ["RADBRIDGE_TEST_DATABASE_URL"]')
            fixture.write_text(content,encoding="utf-8")
            env.update(DATABASE_URL=dsn,RADBRIDGE_TEST_DATABASE_URL=dsn)
            targets=["tests/test_radiotherapy.py","tests/test_case_readiness_service.py","tests/test_domain_readiness.py","tests/test_clinical_app_factory.py",
                     "tests/test_readiness_resolution_dependencies.py","tests/test_readiness_resolution_runtime.py","tests/test_readiness_search_dependencies.py","tests/test_readiness_search_runtime.py"]
            if args.postgres_suite == "assignment":
                targets=["tests/test_assignment_transaction_dependencies.py", "tests/test_visit_service_dependencies.py", "tests/test_distribution_domain.py",
                         "tests/test_assignment_visit_grouping.py", "tests/test_case_assignment_service.py"]
            elif args.postgres_suite == "scope":
                targets=["tests/test_scope_dependencies.py", "tests/test_clinical_scope.py", "tests/test_clinical_app_factory.py"]
            elif args.postgres_suite == "reporting":
                targets=["tests/test_revision_workflow_dependencies.py", "tests/test_report_edit_lease_dependencies.py", "tests/test_report_commit_policy.py", "tests/test_report_commit_dependencies.py",
                         "tests/test_report_commit_runtime.py", "tests/test_report_revisions.py",
                         "tests/test_report_identity_renewal.py", "tests/test_onlyoffice_callback_internal_download_url.py"]
            elif args.postgres_suite == "finance":
                targets=["tests/test_settlement_workflow_dependencies.py", "tests/test_replacement_settlements.py"]
            elif args.postgres_suite == "inventory":
                targets=["tests/test_inventory_return_dependencies.py", "tests/test_inventory_safety.py"]
            elif args.postgres_suite == "registration":
                targets=["tests/test_registration_dependencies.py", "tests/test_registration_policy.py",
                         "tests/test_insurance_readiness_dependencies.py", "tests/test_insurance_work_order.py"]
        else:
            source=ROOT/"ris";env["DATABASE_URL"]="sqlite:///:memory:"
            targets=args.targets
        return subprocess.call([sys.executable,"-m","pytest","-q","--disable-warnings","--tb=short",*targets],cwd=source,env=env)

if __name__=="__main__":raise SystemExit(main())
