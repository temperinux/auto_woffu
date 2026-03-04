"""
Probe — verifica signs endpoint y si acepta fecha para backfill
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

# Login
r = requests.post(
    "https://app.woffu.com/api/svc/accounts/authorization/token",
    data={"grant_type": "password", "username": USER, "password": PASSWORD},
    headers={"Content-Type": "application/x-www-form-urlencoded"},
    timeout=15, proxies=PROXIES,
)
token = r.json().get("accessToken")
p     = json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "=="))
uid   = int(p.get("UserId"))
print(f"✅ Login OK. UserId={uid}")

hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# ── SIGNS POST: endpoint confirmado ──────────────────────────
sep("1. SIGNS POST — endpoint confirmado /api/svc/signs/signs")

base_payload = {
    "agreementEventId": None,
    "requestId":        None,
    "deviceId":         "WebApp",
    "latitude":         None,
    "longitude":        None,
    "timezoneOffset":   -60,
}

# Primero confirmamos que el endpoint funciona (ficha AHORA — cancela/borra después si no quieres)
r = requests.post(f"{BASE}/api/svc/signs/signs",
    json=base_payload, headers=hdrs, timeout=15, proxies=PROXIES)
print(f"  [{r.status_code}] POST sin fecha (hora actual) → {r.text[:300]}")

# ── BACKFILL: ¿acepta fecha? ──────────────────────────────────
sep("2. BACKFILL — ¿acepta campo 'date' o 'signDate' para fechas pasadas?")

# Probamos añadir fecha al payload — usamos una fecha futura inofensiva
DATE_TEST = "2099-01-02T09:35:00"

attempts = [
    ("con 'date'",          {**base_payload, "date": DATE_TEST}),
    ("con 'signDate'",      {**base_payload, "signDate": DATE_TEST}),
    ("con 'Date'",          {**base_payload, "Date": DATE_TEST}),
    ("con 'dateTime'",      {**base_payload, "dateTime": DATE_TEST}),
    ("con 'clockDate'",     {**base_payload, "clockDate": DATE_TEST}),
]

for label, payload in attempts:
    r = requests.post(f"{BASE}/api/svc/signs/signs",
        json=payload, headers=hdrs, timeout=15, proxies=PROXIES)
    mark = "✅" if r.status_code in (200, 201) else "❌"
    resp_preview = r.text[:150]
    print(f"  {mark} [{r.status_code}] {label} → {resp_preview}")

# ── SIGNS GET: ¿podemos leer fichajes? ───────────────────────
sep("3. SIGNS GET — leer fichajes existentes")

today     = date.today()
week_from = today - timedelta(days=today.weekday())
week_to   = week_from + timedelta(days=4)

for path in [
    f"/api/svc/signs/signs?fromDate={week_from}&toDate={week_to}",
    f"/api/svc/signs/signs?userId={uid}&fromDate={week_from}&toDate={week_to}",
    f"/api/svc/signs/users/{uid}/signs?fromDate={week_from}&toDate={week_to}",
]:
    r = requests.get(BASE + path, headers=hdrs, timeout=15, proxies=PROXIES)
    mark = "✅" if r.status_code == 200 else "  "
    print(f"  {mark} [{r.status_code}] GET {path.split('?')[0]}")
    if r.status_code == 200:
        print(f"       {r.text[:200]}")