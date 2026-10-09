
import os, sys, json, requests

BASE=os.getenv("TEST_BASE_URL","http://127.0.0.1:18090").rstrip("/")
TIMEOUT=10

checks=[]

def check(name, fn):
    try:
        fn()
        checks.append((name,"PASS",""))
        print(f"{name:<28} PASS")
    except Exception as e:
        checks.append((name,"FAIL",str(e)))
        print(f"{name:<28} FAIL  {e}")

def get(path, expected=(200,302,401,403)):
    r=requests.get(BASE+path,timeout=TIMEOUT,allow_redirects=False)
    if r.status_code not in expected:
        raise RuntimeError(f"{path} HTTP {r.status_code}")
    return r

check("Health", lambda: (
    (lambda r: (_ for _ in ()).throw(RuntimeError(r.text[:300])) if not r.ok or not r.json().get("ok") else None)
    (requests.get(BASE+"/api/reporting/health",timeout=TIMEOUT))
))

for name,path in [
    ("Login Page","/login"),
    ("Patients","/patients"),
    ("Orders","/orders"),
    ("Technician","/technician"),
    ("Nursing","/nursing"),
    ("PACS Tracking","/pacs/tracking"),
    ("PACS Matching","/pacs/reconciliation"),
    ("Financial Reports","/accounting/financial-center"),
    ("QA Page","/admin/qa"),
]:
    check(name, lambda p=path: get(p))

failed=[x for x in checks if x[1]=="FAIL"]
print("\n===== FULL WORKFLOW SMOKE RESULT =====")
print(f"TOTAL: {len(checks)}  PASS: {len(checks)-len(failed)}  FAIL: {len(failed)}")
if failed:
    for x in failed: print("FAILED:",x[0],x[2])
    sys.exit(1)
print("FULL WORKFLOW SMOKE: PASS")
