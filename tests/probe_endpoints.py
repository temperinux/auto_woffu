"""
Probe — verifies all endpoints used by woffu.py
"""
import requests, os, base64, json, sys
from datetime import date, timedelta

DOMAIN   = os.environ.get("WOFFU_DOMAIN", "gtd.woffu.com").replace("https://","").strip("/")
USER     = os.environ.get("WOFFU_USER", "")
PASSWORD = os.environ.get("WOFFU_PASS", "")
BASE     = f"https://{DOMAIN}"
PROXIES  = {k: v for k, v in {
    "http":  os.environ.get("HTTP_PROXY")  or os.environ.get("http_proxy"),
    "https": os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"),
}.items() if v}

def sep(title): print(f"\n{'─'*55}\n  {title}\n{'─'*55}")

# ── 1. LOGIN ──────────────────────────────────────────────────
sep("1. LOGIN")

r = requests.post(
    "https://app.woffu.com/api/svc/accounts/authorization/token",
    data={"grant_type": "password", "username": USER, "password": PASSWORD},
    headers={"Content-Type": "application/x-www-form-urlencoded"},
    timeout=15, proxies=PROXIES,
)
print(f"  Status: {r.status_code}")
body = r.json()
print(f"  Response keys: {list(body.keys())}")

token = None
for key in ("accessToken", "access_token", "token", "jwtToken", "jwt", "id_token"):
    if body.get(key):
        token = body[key]
        print(f"  ✅ Token found at key '{key}' ({len(token)} chars)")
        break

if not token:
    print("  ❌ Token not found. Available keys:", list(body.keys()))
    sys.exit(1)

p   = json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "=="))
uid = int(p.get("UserId") or p.get("nameid") or p.get("sub"))
print(f"  UserId={uid} | CompanyId={p.get('CompanyId')}")

hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# ── 2. DIARIES ────────────────────────────────────────────────
sep("2. DIARIES")

today     = date.today()
week_from = today - timedelta(days=today.weekday())
week_to   = week_from + timedelta(days=6)

r = requests.get(
    f"{BASE}/api/svc/core/diariesquery/users/{uid}/diaries/summary/presence",
    params={"userId": uid, "fromDate": week_from.strftime("%Y-%m-%d"),
            "toDate": week_to.strftime("%Y-%m-%d"), "pageSize": 7,
            "includeHourTypes": "true", "includeDifference": "true"},
    headers=hdrs, timeout=15, proxies=PROXIES,
)
print(f"  Status: {r.status_code}")
if r.status_code == 200:
    diaries = r.json().get("diaries", [])
    print(f"  ✅ {len(diaries)} days received")
    for d in diaries:
        flag   = "🎉" if d["isHoliday"] else ("📅" if d["isWeekend"] else "💼")
        in_val = d.get("in") or ""
        signed = "✅ clocked" if (in_val and ":" in in_val and not in_val.startswith("_")) else "— not clocked"
        print(f"     {flag} {d['date'][:10]}  holiday={d['isHoliday']}  weekend={d['isWeekend']}  in={in_val!r}  {signed}")
else:
    print(f"  ❌ {r.text[:300]}")

# ── 3. SIGNS POST ─────────────────────────────────────────────
sep("3. SIGNS POST (date 2099 = harmless)")

for url, payload in [
    (f"{BASE}/api/svc/signs/signs",
     {"agreementEventId": None, "requestId": None, "deviceId": "WebApp",
      "latitude": None, "longitude": None, "timezoneOffset": -60,
      "date": "2099-01-02T09:35:00"}),
]:
    r = requests.post(url, json=payload, headers=hdrs, timeout=15, proxies=PROXIES)
    mark = "✅" if r.status_code in (200, 201) else "❌"
    print(f"  {mark} [{r.status_code}] POST {url.replace(BASE,'')} → {r.text[:200]}")