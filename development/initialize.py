"""Explicit fresh-development initialization; never a production migrator."""
import os
from pathlib import Path
import runpy
import sys
from urllib.parse import urlsplit

def validate():
    if os.environ.get("RADBRIDGE_DEVELOPMENT")!="1":raise RuntimeError("Development opt-in required")
    url=urlsplit(os.environ.get("DATABASE_URL",""))
    if url.scheme!="postgresql+psycopg2" or url.hostname!="db" or url.username!="radbridge_dev" or url.path!="/radbridge_dev":
        raise RuntimeError("Initializer only accepts the Compose-local radbridge_dev database")
    if os.environ.get("RADBRIDGE_BOOTSTRAP_ON_IMPORT")!="0":raise RuntimeError("Automatic import bootstrap must stay disabled")

if __name__=="__main__":
    validate()
    # Image places RIS at /app, this initializer at /app/development.
    root=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(root))
    runpy.run_path(str(root/"bootstrap_db.py"),run_name="__main__")
