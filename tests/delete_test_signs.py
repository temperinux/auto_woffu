"""
Borra los fichajes de prueba creados por el probe (fecha 2099-01-02)
"""
import requests, os, base64, json

DOMAIN   = os.environ.get("WOFFU_DOMAIN", "gtd.woffu.com").replace("https://","").strip("/")
USER     = os.environ.get("WOFFU_USER", "")
PASSWORD = os.environ.get("WOFFU_PASS", "")
BASE     = f"https://{DOMAIN}"
PROXIES  = {k: v for k, v in {
    "http":  os.environ.get("HTTP_PROXY")  or os.environ.get("http_proxy"),
    "https": os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"),
}.items() if v}

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

# IDs creados por el probe — cópialos aquí si son distintos
sign_ids = [
    "fb33aad2-239b-4722-8f63-8f46e43c7769",
    "4074f2d0-ed97-45b6-85c0-f99fb8ea5131",
    "3ec12367-4ead-4fcc-bae9-80a31ff158a0",
    "c8dffa3f-75b1-457f-bd8a-a1707e79c747",
    "c472d2d1-f862-4178-871d-b39be122e4e2",  # el de "sin fecha" (hora actual de hoy)
]

print("🗑️  Borrando fichajes de prueba...\n")
for sign_id in sign_ids:
    # Probamos los endpoints de DELETE más probables
    for url in [
        f"{BASE}/api/svc/signs/signs/{sign_id}",
        f"{BASE}/api/v1/signs/{sign_id}",
    ]:
        r = requests.delete(url, headers=hdrs, timeout=15, proxies=PROXIES)
        if r.status_code in (200, 204):
            print(f"  ✅ Borrado {sign_id[:8]}... via {url.replace(BASE,'')}")
            break
        elif r.status_code == 404:
            continue
        else:
            print(f"  ❌ [{r.status_code}] {url.replace(BASE,'')} → {r.text[:150]}")
    else:
        print(f"  ⚠️  No se pudo borrar {sign_id[:8]}... — bórralo manualmente en Woffu")

print("\nHecho.")