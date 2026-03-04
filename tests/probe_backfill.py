"""
Probe — tests the backfill endpoint for a specific past date.
Edit TEST_DATE to a working day with no absence before running.
"""
import requests, os, base64, json, time

DOMAIN   = os.environ.get("WOFFU_DOMAIN", "gtd.woffu.com").replace("https://","").strip("/")
USER     = os.environ.get("WOFFU_USER", "")
PASSWORD = os.environ.get("WOFFU_PASS", "")
BASE     = f"https://{DOMAIN}"
PROXIES  = {k: v for k, v in {
    "http":  os.environ.get("HTTP_PROXY")  or os.environ.get("http_proxy"),
    "https": os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"),
}.items() if v}

# ── Config ────────────────────────────────────────────────────
TEST_DATE  = "2026-02-25"   # change to a past working day with no absence
ENTRY_TIME = "09:28:00"
EXIT_TIME  = "18:31:00"

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
print(f"✅ Login OK. UserId={uid}\n")

hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# Calculate total minutes
eh, em = int(ENTRY_TIME.split(":")[0]), int(ENTRY_TIME.split(":")[1])
oh, om = int(EXIT_TIME.split(":")[0]),  int(EXIT_TIME.split(":")[1])
total_min = (oh * 60 + om) - (eh * 60 + em)

payload = {
    "date":     TEST_DATE,
    "comments": "",
    "userId":   uid,
    "slots": [{
        "id":     str(int(time.time() * 1000)),
        "motive": None,
        "in": {
            "new": True, "deleted": False, "agreementEventId": None,
            "code": None, "iP": None, "requestId": None, "signId": 0,
            "signStatus": 1, "signType": 3, "time": ENTRY_TIME,
            "deviceId": None, "signIn": True, "userId": 0,
        },
        "out": {
            "new": True, "deleted": False, "agreementEventId": None,
            "code": None, "iP": None, "requestId": None, "signId": 0,
            "signStatus": 1, "signType": 3, "time": EXIT_TIME,
            "deviceId": None, "signIn": False, "userId": 0,
        },
        "order": 1, "totalMin": total_min,
    }],
}

print(f"📅 Testing PUT for {TEST_DATE} ({ENTRY_TIME} - {EXIT_TIME})...")
r = requests.put(
    f"{BASE}/api/svc/core/users/{uid}/diarysummaries/workday/slots/self",
    json=payload, headers=hdrs, timeout=15, proxies=PROXIES,
)
print(f"  Status: {r.status_code}")
print(f"  Response: {r.text[:400]}")

if r.status_code == 200:
    print(f"\n✅ Works! Check in Woffu that {TEST_DATE} shows {ENTRY_TIME} - {EXIT_TIME}")
else:
    print(f"\n❌ Failed. The day may already have a sign or the format may differ.")