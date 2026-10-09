
import os, sys
try:
    from playwright.sync_api import sync_playwright
except Exception:
    print("Playwright not installed. Run: pip install playwright && playwright install chromium")
    sys.exit(2)

base=os.getenv("TEST_BASE_URL","http://127.0.0.1:8090").rstrip("/")
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page()
    for path in ["/login","/api/reporting/health"]:
        r=page.goto(base+path,wait_until="domcontentloaded")
        print(path, r.status if r else "NO_RESPONSE")
        if not r or r.status>=500:
            page.screenshot(path=f"/tmp/ris-fail-{path.strip('/').replace('/','_') or 'root'}.png",full_page=True)
            browser.close()
            sys.exit(1)
    browser.close()
print("PLAYWRIGHT SMOKE: PASS")
