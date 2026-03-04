"""
Woffu Bot - Automatic clock-in/out manager
Uso:
  python woffu.py backfill --from 2025-01-01 --to 2025-01-31   # Fill in past clock-ins
  python woffu.py clock --type in                                # Fichar entrada ahora
  python woffu.py clock --type out                               # Fichar salida ahora
"""

import argparse
import base64
import json
import os
import random
import sys
import time
from datetime import datetime, timedelta, date

import requests
import pytz

# ─── Configuración ────────────────────────────────────────────────────────────

WOFFU_DOMAIN = os.environ.get("WOFFU_DOMAIN", "gtd.woffu.com") \
    .replace("https://", "").replace("http://", "").strip("/")
WOFFU_USER   = os.environ.get("WOFFU_USER", "")
WOFFU_PASS   = os.environ.get("WOFFU_PASS", "")

# Horario base
ENTRY_HOUR, ENTRY_MIN = 9, 30
EXIT_HOUR,  EXIT_MIN  = 18, 30

# Variación aleatoria en minutos (entrada: nunca antes de la hora base)
VARIATION_MINUTES = 5

# Zona horaria
TIMEZONE = "Europe/Madrid"

# Proxy — se lee automáticamente de las variables de entorno del sistema
PROXIES = {k: v for k, v in {
    "http":  os.environ.get("HTTP_PROXY")  or os.environ.get("http_proxy"),
    "https": os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"),
}.items() if v}

# ─── Endpoints (todos confirmados) ────────────────────────────────────────────

AUTH_URL = "https://app.woffu.com/api/svc/accounts/authorization/token"
BASE_URL = f"https://{WOFFU_DOMAIN}"

# ─── API ───────────────────────────────────────────────────────────────────────

def get_token(user: str, password: str) -> str:
    resp = requests.post(
        AUTH_URL,
        data={"grant_type": "password", "username": user, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15, proxies=PROXIES,
    )
    resp.raise_for_status()
    token = resp.json().get("accessToken")
    if not token:
        raise ValueError(f"Could not find 'accessToken' in response: {resp.json()}")
    return token


def get_user_id(token: str) -> int:
    payload_b64 = token.split(".")[1]
    payload_b64 += "=" * (-len(payload_b64) % 4)
    p = json.loads(base64.urlsafe_b64decode(payload_b64))
    uid = p.get("UserId") or p.get("userId") or p.get("nameid")
    if not uid:
        raise ValueError(f"Could not find UserId in token. Claims: {p}")
    return int(uid)


def get_diaries(token: str, user_id: int, from_date: date, to_date: date) -> list:
    """Diario del usuario — contiene isHoliday, isWeekend, absenceEvents e in/out."""
    days = (to_date - from_date).days + 1
    resp = requests.get(
        f"{BASE_URL}/api/svc/core/diariesquery/users/{user_id}/diaries/summary/presence",
        params={
            "userId":            user_id,
            "fromDate":          from_date.strftime("%Y-%m-%d"),
            "toDate":            to_date.strftime("%Y-%m-%d"),
            "pageSize":          days,
            "includeHourTypes":  "true",
            "includeDifference": "true",
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=15, proxies=PROXIES,
    )
    resp.raise_for_status()
    return resp.json().get("diaries", [])


def post_sign_now(token: str) -> str:
    """
    Registers a clock event at the current time.
    Woffu automatically toggles between in and out.
    """
    payload = {
        "agreementEventId": None,
        "requestId":        None,
        "deviceId":         "WebApp",
        "latitude":         None,
        "longitude":        None,
        "timezoneOffset":   -60,
    }
    resp = requests.post(
        f"{BASE_URL}/api/svc/signs/signs",
        json=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=15, proxies=PROXIES,
    )
    resp.raise_for_status()
    return resp.json().get("signEventId", "ok")


def put_workday_slots(token: str, user_id: int, d: date, entry_time: str, exit_time: str) -> dict:
    """
    Creates or overwrites clock-in and clock-out for a past day
    using Woffu's presence editing endpoint.
    """
    # Calculamos totalMin
    eh, em = int(entry_time.split(":")[0]), int(entry_time.split(":")[1])
    oh, om = int(exit_time.split(":")[0]),  int(exit_time.split(":")[1])
    total_min = (oh * 60 + om) - (eh * 60 + em)

    slot_id = str(int(time.time() * 1000))

    payload = {
        "date":     d.strftime("%Y-%m-%d"),
        "comments": "",
        "userId":   user_id,
        "slots": [
            {
                "id":     slot_id,
                "motive": None,
                "in": {
                    "new":              True,
                    "deleted":          False,
                    "agreementEventId": None,
                    "code":             None,
                    "iP":               None,
                    "requestId":        None,
                    "signId":           0,
                    "signStatus":       1,
                    "signType":         3,
                    "time":             entry_time,
                    "deviceId":         None,
                    "signIn":           True,
                    "userId":           0,
                },
                "out": {
                    "new":              True,
                    "deleted":          False,
                    "agreementEventId": None,
                    "code":             None,
                    "iP":               None,
                    "requestId":        None,
                    "signId":           0,
                    "signStatus":       1,
                    "signType":         3,
                    "time":             exit_time,
                    "deviceId":         None,
                    "signIn":           False,
                    "userId":           0,
                },
                "order":    1,
                "totalMin": total_min,
            }
        ],
    }

    resp = requests.put(
        f"{BASE_URL}/api/svc/core/users/{user_id}/diarysummaries/workday/slots/self",
        json=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=15, proxies=PROXIES,
    )
    resp.raise_for_status()
    return resp.json() if resp.text else {"status": "ok"}


# ─── Lógica de calendario ─────────────────────────────────────────────────────

def classify_diaries(diaries: list) -> tuple[set, set]:
    """
    Classifies diary dates into:
    - already_signed: 'in' field has a real time (HH:MM:SS)
    - skip_days:      holidays, weekends or absences
    """
    already_signed = set()
    skip_days      = set()

    for d in diaries:
        date_str = (d.get("date") or "")[:10]
        if not date_str:
            continue

        if d.get("isHoliday") or d.get("isWeekend"):
            skip_days.add(date_str)
            continue

        if d.get("absenceEvents"):
            skip_days.add(date_str)
            continue

        in_val = d.get("in") or ""
        if in_val and ":" in in_val and not in_val.startswith("_"):
            already_signed.add(date_str)

    return already_signed, skip_days


# ─── Helpers ──────────────────────────────────────────────────────────────────

def random_time(hour: int, minute: int, allow_before: bool = True) -> str:
    """Devuelve HH:MM:SS con variación aleatoria. Si allow_before=False, offset solo positivo."""
    offset = (
        random.randint(0, VARIATION_MINUTES)
        if not allow_before
        else random.randint(-VARIATION_MINUTES, VARIATION_MINUTES)
    )
    dt = datetime(2000, 1, 1, hour, minute) + timedelta(minutes=offset)
    return dt.strftime("%H:%M:%S")


def auth() -> tuple[str, int]:
    user = WOFFU_USER or input("Woffu user (email): ")
    pwd  = WOFFU_PASS or input("Password: ")
    print("🔑 Authenticating...")
    token   = get_token(user, pwd)
    user_id = get_user_id(token)
    print(f"✅ Authenticated. UserId={user_id}")
    return token, user_id


# ─── Comandos ──────────────────────────────────────────────────────────────────

def cmd_clock(args):
    """Clock in or out now (uses Woffu's automatic toggle)."""
    token, _ = auth()
    label    = "IN" if args.type == "in" else "OUT"
    print(f"⏱  Clocking {label}...")
    sign_id = post_sign_now(token)
    tz  = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    print(f"✅ {label} clocked: {now.strftime('%Y-%m-%d %H:%M')} (id={sign_id})")


def cmd_backfill(args):
    """
    Fills in clock-in and clock-out for a date range, skipping:
      • Public holidays from Woffu calendar    (isHoliday)
      • Weekends                               (isWeekend)
      • Days with absences/vacation            (absenceEvents)
      • Days already clocked                   ('in' field has real time)
    """
    token, user_id = auth()

    from_date = date.fromisoformat(args.from_date)
    to_date   = date.fromisoformat(args.to_date)

    if from_date > to_date:
        print("❌ Start date is after end date.")
        sys.exit(1)

    print(f"\n📅 Fetching Woffu diary ({from_date} → {to_date})...")
    try:
        diaries        = get_diaries(token, user_id, from_date, to_date)
        already_signed, skip_days = classify_diaries(diaries)
        diary_by_date  = {(d.get("date") or "")[:10]: d for d in diaries}
        print(f"   → {len(diaries)} days in diary")
        print(f"   → {len(already_signed)} already clocked")
        print(f"   → {len(skip_days)} non-working days (holidays / weekends / absences)")
    except Exception as e:
        print(f"❌ Error fetching diary: {e}")
        sys.exit(1)

    current = from_date
    created = 0
    skipped = 0
    errors  = 0

    print("\n🗓️  Procesando...\n")

    while current <= to_date:
        date_str = current.strftime("%Y-%m-%d")
        d        = diary_by_date.get(date_str, {})

        # Fines de semana: silencioso
        if d.get("isWeekend"):
            current += timedelta(days=1)
            continue

        # Festivos
        if d.get("isHoliday"):
            print(f"  🎉 {date_str} — public holiday ({d.get('name', '')}), skipped")
            skipped += 1
            current += timedelta(days=1)
            continue

        # Ausencias/vacaciones
        if d.get("absenceEvents"):
            print(f"  🏖️  {date_str} — registered absence, skipped")
            skipped += 1
            current += timedelta(days=1)
            continue

        # Ya fichado
        if date_str in already_signed:
            print(f"  ✅ {date_str} — already clocked ({d.get('in', '')}), skipped")
            skipped += 1
            current += timedelta(days=1)
            continue

        # No encontrado en el diario
        if not d:
            print(f"  ⚠️  {date_str} — not found in diary, skipped")
            skipped += 1
            current += timedelta(days=1)
            continue

        # Fichar entrada y salida
        entry_time = random_time(ENTRY_HOUR, ENTRY_MIN - 5, allow_before=True)  # 9:25 ±5 → 9:20–9:30
        exit_time  = random_time(EXIT_HOUR,  EXIT_MIN,  allow_before=True)

        try:
            put_workday_slots(token, user_id, current, entry_time, exit_time)
            print(f"  🟢 {date_str} — in {entry_time[:5]} | out {exit_time[:5]}")
            created += 1
        except Exception as e:
            print(f"  ❌ {date_str} — error: {e}")
            errors += 1

        current += timedelta(days=1)

    print(f"\n{'─'*50}")
    print(f"📊 Summary:")
    print(f"   🟢 Created:  {created} days clocked")
    print(f"   ⏭  Skipped: {skipped} days")
    print(f"   ❌ Errors:   {errors} days")
    print(f"{'─'*50}")


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Woffu Bot — clock-in/out manager")
    sub = parser.add_subparsers(dest="command", required=True)

    p_clock = sub.add_parser("clock", help="Clock in or out now")
    p_clock.add_argument("--type", choices=["in", "out"], required=True)

    p_back = sub.add_parser("backfill", help="Fill in past clock-ins")
    p_back.add_argument("--from", dest="from_date", required=True, help="Start date YYYY-MM-DD")
    p_back.add_argument("--to",   dest="to_date",   required=True, help="End date YYYY-MM-DD")

    args = parser.parse_args()

    if args.command == "clock":
        cmd_clock(args)
    elif args.command == "backfill":
        cmd_backfill(args)


if __name__ == "__main__":
    main()