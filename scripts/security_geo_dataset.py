"""Download a public country dataset; never transmit client addresses."""
import csv
import gzip
import hashlib
import io
import ipaddress
import json
import os
import sqlite3
import urllib.request
from pathlib import Path

def build(destination, url, expected_md5, release):
    assert url.startswith('https://download.db-ip.com/free/dbip-country-lite-') and url.endswith('.csv.gz')
    request = urllib.request.Request(url, headers={'User-Agent':'RadBridge-Security/1.0 (+https://rispacs.radbridges.com)'})
    with urllib.request.urlopen(request, timeout=90) as response:
        compressed = response.read(30 * 1024 * 1024)
        assert not response.read(1), 'Country download exceeded configured bound'
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as gz:
        raw = gz.read(64 * 1024 * 1024)
        assert not gz.read(1), 'Uncompressed dataset exceeded configured bound'
    # DB-IP publishes checksums for the CSV, not for its gzip transport wrapper.
    assert hashlib.md5(raw).hexdigest() == expected_md5, 'Published provider CSV checksum mismatch'
    target = Path(destination)
    tmp = target.with_suffix('.building')
    assert not tmp.exists(), 'Inspect previous partial dataset before retrying'
    c = sqlite3.connect(tmp)
    try:
        c.execute('CREATE TABLE ranges(version INTEGER,first TEXT,last TEXT,country TEXT,PRIMARY KEY(version,first)) WITHOUT ROWID')
        c.execute('CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT)')
        count, batch = 0, []
        with io.StringIO(raw.decode('utf-8')) as stream:
            for first, last, code in csv.reader(stream):
                lo, hi = ipaddress.ip_address(first), ipaddress.ip_address(last)
                assert lo.version == hi.version and lo <= hi and len(code) == 2 and code.isupper()
                batch.append((lo.version, f'{int(lo):032x}', f'{int(hi):032x}', code))
                count += 1
                if len(batch) == 2000:
                    c.executemany('INSERT INTO ranges VALUES(?,?,?,?)', batch); batch = []
            if batch: c.executemany('INSERT INTO ranges VALUES(?,?,?,?)', batch)
        assert count > 100000
        c.executemany('INSERT INTO metadata VALUES(?,?)', [('release_date',release), ('provider','DB-IP Lite'), ('license','CC BY 4.0'), ('source_sha256',hashlib.sha256(compressed).hexdigest()), ('records',str(count))])
        c.commit()
        assert c.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    finally:
        c.close()
    tmp.chmod(0o600)
    os.replace(tmp, target)
    return {'records':count, 'sha256':hashlib.sha256(target.read_bytes()).hexdigest(), 'provider_checksum_verified':True, 'release':release}

if __name__ == '__main__':
    import sys
    print(json.dumps(build(sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4])))
