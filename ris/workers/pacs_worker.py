"""RadBridge PACS background worker.

Runs automatic PACS intake and processes queued DICOM transfer jobs. Keep this
worker idempotent: a crash/restart must not delete source studies or lose queue
state. Queue state itself is persisted in PostgreSQL through the main app models.
"""
import os
import time
from app import app, db, pacs_auto_intake_once, process_pacs_transfer_jobs

interval = max(10, int(os.getenv("PACS_WORKER_INTERVAL_SECONDS", "30")))

with app.app_context():
    while True:
        try:
            # Intake first so newly arrived Orthanc studies can be reconciled before routing.
            result = pacs_auto_intake_once(300)
            transferred = process_pacs_transfer_jobs(30)
            print("PACS_WORKER", result, "transfers", transferred, flush=True)
        except Exception as exc:
            # Always rollback the SQLAlchemy session so the next loop starts cleanly.
            db.session.rollback()
            print("PACS_WORKER_ERROR", exc, flush=True)
        time.sleep(interval)
