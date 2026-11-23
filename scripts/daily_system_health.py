#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AirScan / RadBridge Daily System Health & Log Inspector
Runs twice daily (Morning 08:00 & Evening 20:00)
Scans system logs, detects errors, performs auto-recovery, and generates reports.
"""
import os
import sys
import json
import time
import datetime
import subprocess
import urllib.request
import base64

REPORT_DIR = "/home/rispacs/RadBridge_Final/logs/health_reports"
os.makedirs(REPORT_DIR, exist_ok=True)

NOW = datetime.datetime.now()
TIMESTAMP_STR = NOW.strftime("%Y%m%d_%H%M%S")
REPORT_FILE_JSON = os.path.join(REPORT_DIR, f"health_{TIMESTAMP_STR}.json")
REPORT_FILE_MD = os.path.join(REPORT_DIR, f"health_{TIMESTAMP_STR}.md")
LATEST_MD = os.path.join(REPORT_DIR, "latest_health.md")

results = {
    "timestamp": NOW.isoformat(),
    "period": "Morning (صباحاً)" if NOW.hour < 14 else "Evening (آخر اليوم)",
    "containers": {},
    "services": {},
    "disk_memory": {},
    "errors_detected": [],
    "actions_taken": [],
    "status": "HEALTHY"
}

def run_cmd(cmd):
    try:
        p = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except Exception as e:
        return -1, "", str(e)

print(f"=== AirScan Daily Log & Health Check [{results['period']}] - {NOW.strftime('%Y-%m-%d %H:%M:%S')} ===")

# 1. Check Containers
CONTAINER_NAMES = [
    "ris-web", "radbridge-orthanc", "radbridge-postgres",
    "radbridge-nginx", "radbridge-mirth", "radbridge-ohif", "radbridge-ohif-app"
]

rc, out, _ = run_cmd("docker ps -a --format '{{.Names}}\t{{.Status}}'")
running_map = {}
for line in out.splitlines():
    if "\t" in line:
        name, st = line.split("\t", 1)
        running_map[name] = st

for c in CONTAINER_NAMES:
    st = running_map.get(c, "NOT_FOUND")
    is_up = "Up" in st
    results["containers"][c] = {"status": st, "is_up": is_up}
    if not is_up:
        results["errors_detected"].append(f"Container {c} is not running: {st}")
        print(f"[!] Warning: Container {c} is down ({st}). Attempting restart...")
        run_cmd(f"docker start {c}")
        results["actions_taken"].append(f"Restarted container {c}")

# 2. Check RIS Web HTTP
try:
    req = urllib.request.Request("http://127.0.0.1:8090/login", headers={"User-Agent": "AirScanHealthCheck/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        results["services"]["ris_web"] = {"code": r.status, "status": "UP"}
except Exception as e:
    results["services"]["ris_web"] = {"error": str(e), "status": "DOWN"}
    results["errors_detected"].append(f"RIS Web HTTP failure: {e}")

# 3. Check Orthanc PACS REST API
try:
    auth = base64.b64encode(b"admin:admin").decode("ascii")
    req = urllib.request.Request("http://localhost:8042/system", headers={"Authorization": f"Basic {auth}"})
    with urllib.request.urlopen(req, timeout=10) as r:
        s_data = json.loads(r.read().decode())
        results["services"]["orthanc_pacs"] = {
            "status": "UP",
            "version": s_data.get("Version"),
            "compression": s_data.get("StorageCompression"),
            "ingest_transcoding": s_data.get("IngestTranscoding")
        }
except Exception as e:
    results["services"]["orthanc_pacs"] = {"error": str(e), "status": "DOWN"}
    results["errors_detected"].append(f"Orthanc PACS API failure: {e}")

# 4. Check Postgres DB
rc, out, _ = run_cmd("docker exec radbridge-postgres pg_isready -U postgres")
if rc == 0:
    results["services"]["postgres"] = {"status": "UP", "msg": out}
else:
    results["services"]["postgres"] = {"status": "DOWN", "error": out}
    results["errors_detected"].append(f"PostgreSQL failure: {out}")

# 5. Check Disk & Memory
rc, out, _ = run_cmd("df -h / | tail -n 1")
if rc == 0:
    parts = out.split()
    results["disk_memory"]["disk_used_percent"] = parts[4]
    results["disk_memory"]["disk_available"] = parts[3]
    use_num = int(parts[4].replace("%", ""))
    if use_num > 85:
        results["errors_detected"].append(f"High Disk Usage: {parts[4]} used ({parts[3]} free)")

rc, out, _ = run_cmd("free -m | grep Mem:")
if rc == 0:
    parts = out.split()
    results["disk_memory"]["memory_total_mb"] = parts[1]
    results["disk_memory"]["memory_available_mb"] = parts[6]
    if int(parts[6]) < 400:
        results["errors_detected"].append(f"Low Available Memory: {parts[6]} MB free")

# 6. Deep Scan Container Logs
log_targets = [
    ("ris-web", 300, ["Traceback", "Exception", "Internal Server Error", "HTTP/1.1 500"]),
    ("radbridge-orthanc", 200, ["FATAL", "Crash"]),
    ("radbridge-nginx", 200, [" [error] ", " 500 ", " 502 ", " 504 "]),
    ("radbridge-postgres", 100, ["FATAL", "PANIC"])
]

log_anomalies = {}
for cname, lines, patterns in log_targets:
    rc, out, _ = run_cmd(f"docker logs --tail {lines} {cname} 2>&1")
    matched = []
    if rc == 0 and out:
        for line in out.splitlines():
            if "head -c" in line or "curl/7" in line:
                continue
            if any(p.lower() in line.lower() for p in patterns):
                matched.append(line)
    if matched:
        log_anomalies[cname] = matched[:10]
        results["errors_detected"].append(f"Container {cname} logged {len(matched)} errors/warnings")

results["log_anomalies"] = log_anomalies

if results["errors_detected"]:
    results["status"] = "WARNING" if all("logged" in e or "Warning" in e for e in results["errors_detected"]) else "CRITICAL"
else:
    results["status"] = "PERFECT_HEALTH"

# Write JSON report
with open(REPORT_FILE_JSON, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

# Write Markdown report
md = f"""# تقرير فحص النظام واللوج اليومي - AirScan / RadBridge
**الفترة:** {results['period']}  
**التاريخ والوقت:** {NOW.strftime('%Y-%m-%d %H:%M:%S')}  
**الحالة العامة للنظام:** {'✅ سليم ومستقر 100%' if results['status'] == 'PERFECT_HEALTH' else '⚠️ يوجد ملاحظات تحتاج مراجعة'}

---

## 1. حالة الحاويات والخدمات (Containers & Services)
| الخدمة | الحالة | الملاحظات |
| :--- | :--- | :--- |
| **RIS Web Application** | {'✅ تعمل' if results['services'].get('ris_web', {}).get('status') == 'UP' else '❌ متوقفة'} | HTTP {results['services'].get('ris_web', {}).get('code', 'Error')} |
| **Orthanc PACS Server** | {'✅ تعمل' if results['services'].get('orthanc_pacs', {}).get('status') == 'UP' else '❌ متوقفة'} | JPEG 2000 Lossless ({results['services'].get('orthanc_pacs', {}).get('ingest_transcoding', 'Active')}) |
| **PostgreSQL Database** | {'✅ تعمل' if results['services'].get('postgres', {}).get('status') == 'UP' else '❌ متوقفة'} | Ready & Healthy |
| **Nginx Web Gateway** | {'✅ تعمل' if results['containers'].get('radbridge-nginx', {}).get('is_up') else '❌ متوقفة'} | Port 80, 443, 8090 |
| **OHIF Viewer** | {'✅ تعمل' if results['containers'].get('radbridge-ohif', {}).get('is_up') else '❌ متوقفة'} | Ready |

---

## 2. موارد السيرفر (Server Resources)
* **المساحة التخزينية:** استخدام {results['disk_memory'].get('disk_used_percent', 'N/A')} (المتبقي: {results['disk_memory'].get('disk_available', 'N/A')})
* **الذاكرة العشوائية (RAM):** المتبقي المتاح {results['disk_memory'].get('memory_available_mb', 'N/A')} ميجابايت من أصل {results['disk_memory'].get('memory_total_mb', 'N/A')} ميجابايت

---

## 3. نتائج فحص اللوج (Log Inspection Results)
"""

if not results["errors_detected"]:
    md += "\n✅ **لم يتم رصد أي أخطاء حرجة أو استثناءات في اللوج.** جميع السجلات طبيعية والخدمات تعمل بكفاءة تامة.\n"
else:
    md += "\nتم رصد الملاحظات التالية:\n"
    for err in results["errors_detected"]:
        md += f"* ⚠️ {err}\n"

if results["actions_taken"]:
    md += "\n### الإجراءات التلقائية المنفذة للتعافي الذكي (Self-Healing):\n"
    for act in results["actions_taken"]:
        md += f"* 🔧 {act}\n"

with open(REPORT_FILE_MD, "w", encoding="utf-8") as f:
    f.write(md)

with open(LATEST_MD, "w", encoding="utf-8") as f:
    f.write(md)

print(f"Report generated: {REPORT_FILE_MD}")
print(f"Overall Status: {results['status']}")
