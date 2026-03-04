"""
Woffu Bot - Gestión de fichajes automáticos
Uso:
  python woffu.py backfill --from 2025-01-01 --to 2025-01-31   # Rellenar fichajes pasados
  python woffu.py clock --type in                                # Fichar entrada ahora
  python woffu.py clock --type out                               # Fichar salida ahora
  python woffu.py inspect --date 2025-01-06                      # Ver raw del diary de un día
"""

import argparse
import json
import os
import random
import sys
from datetime import datetime, timedelta, date

import requests
import pytz

# ─── Configuración ────────────────────────────────────────────────────────────

_raw_domain   = os.environ.get("WOFFU_DOMAIN", "app.woffu.com")
# Limpiamos el dominio por si incluye el protocolo (https:// o http://)
WOFFU_DOMAIN  = _raw_domain.replace("https://", "").replace("http://", "").rstrip("/")
WOFFU_USER    = os.environ.get("WOFFU_USER", "")
WOFFU_PASS    = os.environ.get("WOFFU_PASS", "")
WOFFU_USER_ID = int(os.environ["WOFFU_USER_ID"]) if os.environ.get("WOFFU_USER_ID") else None

# Proxy: se lee automáticamente de las variables de entorno del sistema
# (HTTPS_PROXY, HTTP_PROXY, https_proxy, http_proxy).
# Si necesitas forzarlo manualmente, descomenta y rellena:
# os.environ["HTTPS_PROXY"] = "http://proxy.miempresa.com:8080"
# os.environ["HTTP_PROXY"]  = "http://proxy.miempresa.com:8080"
PROXIES = {
    "http":  os.environ.get("HTTP_PROXY")  or os.environ.get("http_proxy"),
    "https": os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"),
}
# Eliminamos claves None para no interferir si no hay proxy configurado
PROXIES = {k: v for k, v in PROXIES.items() if v}

# Horario base
ENTRY_HOUR, ENTRY_MIN = 9, 30
EXIT_HOUR,  EXIT_MIN  = 18, 30

# Variación aleatoria en minutos (entrada: nunca antes de la hora base)
VARIATION_MINUTES = 5

# Zona horaria
TIMEZONE = "Europe/Madrid"

# ─── Campos que Woffu puede usar para indicar día no laborable en Diaries.
# El script prueba todos hasta encontrar uno que funcione con tu cuenta.
# Si ninguno funciona, se imprimirá el raw del diary para que puedas identificarlo.
NON_WORKING_FIELDS = [
    "IsHoliday",
    "isHoliday",
    "IsPublicHoliday",
    "isPublicHoliday",
    "IsNonWorkingDay",
    "isNonWorkingDay",
    "NonWorking",
    "IsWorkingDay",   # este es el contrario: True = laborable
    "isWorkingDay",
    "WorkingDay",
]

# ─── API ───────────────────────────────────────────────────────────────────────

BASE_URL = f"https://{WOFFU_DOMAIN}"


def get_token(user: str, password: str) -> str:
    resp = requests.post(
        f"{BASE_URL}/token",
        data={"grant_type": "password", "username": user, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15, proxies=PROXIES,
    )
    resp.raise_for_status()
    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise ValueError(f"No se pudo obtener token. Respuesta: {data}")
    return token


def get_user_id(token: str) -> int:
    """
    Obtiene el UserId del usuario autenticado.
    Estrategia 1: decodificar el JWT (payload lleva UserId, sin llamada de red).
    Estrategia 2: GET /api/v1/users y buscar por email.
    """
    import base64 as _b64, json as _json

    # Estrategia 1: JWT decode
    try:
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = _json.loads(_b64.urlsafe_b64decode(payload_b64))
        user_id = (
            payload.get("UserId") or payload.get("userId")
            or payload.get("user_id") or payload.get("nameid")
            or payload.get("sub")
        )
        if user_id:
            return int(user_id)
    except Exception:
        pass

    # Estrategia 2: lista de usuarios
    resp = requests.get(
        f"{BASE_URL}/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15, proxies=PROXIES,
    )
    resp.raise_for_status()
    users = resp.json()

    email_lower = WOFFU_USER.lower()
    for u in users:
        email = (u.get("Email") or u.get("email") or u.get("UserName") or "").lower()
        if email == email_lower:
            uid = u.get("UserId") or u.get("userId") or u.get("Id") or u.get("id")
            if uid:
                return int(uid)

    if len(users) == 1:
        u = users[0]
        uid = u.get("UserId") or u.get("userId") or u.get("Id") or u.get("id")
        if uid:
            return int(uid)

    raise ValueError(
        f"No se pudo obtener UserId.\n"
        f"Fíjalo manualmente con: export WOFFU_USER_ID=<tu_id>\n"
        f"Usuarios recibidos: {users}"
    )



def post_sign(token: str, user_id: int, dt: datetime, sign_in: bool) -> dict:
    tz = pytz.timezone(TIMEZONE)
    if dt.tzinfo is None:
        dt = tz.localize(dt)
    resp = requests.post(
        f"{BASE_URL}/api/v1/signs",
        json={
            "UserId": user_id,
            "Date": dt.strftime("%Y-%m-%dT%H:%M:%S"),
            "SignIn": sign_in,
            "TimezoneId": "Romance Standard Time",
        },
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=15, proxies=PROXIES,
    )
    resp.raise_for_status()
    return resp.json() if resp.text else {"status": "ok"}


def get_existing_sign_dates(token: str, user_id: int, from_date: date, to_date: date) -> set:
    resp = requests.get(
        f"{BASE_URL}/api/v1/users/{user_id}/signs",
        params={
            "startDate": from_date.strftime("%Y-%m-%dT00:00:00"),
            "endDate":   to_date.strftime("%Y-%m-%dT23:59:59"),
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=15, proxies=PROXIES,
    )
    resp.raise_for_status()
    days = set()
    for sign in resp.json():
        raw = sign.get("Date") or sign.get("date") or ""
        if raw:
            days.add(raw[:10])
    return days


def get_absence_dates(token: str, user_id: int, from_date: date, to_date: date) -> set:
    """Ausencias y vacaciones registradas en Woffu."""
    resp = requests.get(
        f"{BASE_URL}/api/v1/users/{user_id}/requests",
        params={
            "startDate": from_date.strftime("%Y-%m-%dT00:00:00"),
            "endDate":   to_date.strftime("%Y-%m-%dT23:59:59"),
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=15, proxies=PROXIES,
    )
    resp.raise_for_status()
    absence_dates = set()
    for req in resp.json():
        start_raw = req.get("StartDate") or req.get("startDate") or ""
        end_raw   = req.get("EndDate")   or req.get("endDate")   or ""
        if not start_raw or not end_raw:
            continue
        req_start = date.fromisoformat(start_raw[:10])
        req_end   = date.fromisoformat(end_raw[:10])
        current = req_start
        while current <= req_end:
            if from_date <= current <= to_date:
                absence_dates.add(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)
    return absence_dates


def get_diaries(token: str, user_id: int, from_date: date, to_date: date) -> list:
    """Obtiene los diarios del rango. Cada entrada representa un día."""
    resp = requests.get(
        f"{BASE_URL}/api/v1/users/{user_id}/diaries",
        params={
            "startDate": from_date.strftime("%Y-%m-%dT00:00:00"),
            "endDate":   to_date.strftime("%Y-%m-%dT23:59:59"),
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=15, proxies=PROXIES,
    )
    resp.raise_for_status()
    return resp.json()


def parse_non_working_days(diaries: list, verbose: bool = False) -> tuple[set, str | None]:
    """
    Analiza la respuesta de Diaries e intenta detectar qué campo indica día no laborable.

    Devuelve:
      - set con fechas (YYYY-MM-DD) de días no laborables según Woffu
      - nombre del campo encontrado (o None si no se detectó ninguno)
    """
    if not diaries:
        return set(), None

    # Mostramos el primer diary en modo verbose para que el usuario vea la estructura
    if verbose:
        print("\n📄 Estructura raw del primer diary entry:")
        print(json.dumps(diaries[0], indent=2, ensure_ascii=False))
        print()

    # Intentamos detectar el campo correcto automáticamente
    detected_field = None
    inverted = False  # True si el campo es "IsWorkingDay" (True = laborable)

    first = diaries[0]
    for field in NON_WORKING_FIELDS:
        if field in first:
            detected_field = field
            inverted = field in ("IsWorkingDay", "isWorkingDay", "WorkingDay")
            break

    if not detected_field:
        return set(), None

    # Extraemos las fechas no laborables
    non_working = set()
    for diary in diaries:
        raw_date = diary.get("Date") or diary.get("date") or diary.get("DiaryDate") or ""
        if not raw_date:
            continue
        date_str = raw_date[:10]
        value = diary.get(detected_field)
        if value is None:
            continue
        is_non_working = (not value) if inverted else bool(value)
        if is_non_working:
            non_working.add(date_str)

    return non_working, detected_field


# ─── Helpers ──────────────────────────────────────────────────────────────────

def apply_variation(base_hour: int, base_min: int, allow_before: bool = True) -> datetime:
    tz = pytz.timezone(TIMEZONE)
    today = datetime.now(tz).date()
    offset = (
        random.randint(0, VARIATION_MINUTES)
        if not allow_before
        else random.randint(-VARIATION_MINUTES, VARIATION_MINUTES)
    )
    base_dt = tz.localize(datetime(today.year, today.month, today.day, base_hour, base_min))
    return base_dt + timedelta(minutes=offset)


def is_weekday(d: date) -> bool:
    return d.weekday() < 5


def auth(user=None, pwd=None):
    user = user or WOFFU_USER or input("Usuario Woffu: ")
    pwd  = pwd  or WOFFU_PASS or input("Contraseña: ")
    print("🔑 Autenticando...")
    token   = get_token(user, pwd)
    user_id = WOFFU_USER_ID or get_user_id(token)
    print(f"✅ Autenticado. UserId={user_id}")
    return token, user_id


# ─── Comandos ──────────────────────────────────────────────────────────────────

def cmd_inspect(args):
    """
    Muestra el diary raw de un día concreto.
    Útil para descubrir qué campos devuelve Woffu con tu cuenta.
    """
    token, user_id = auth()
    target = date.fromisoformat(args.date)

    print(f"\n🔍 Consultando diary de {target}...\n")
    diaries = get_diaries(token, user_id, target, target)

    if not diaries:
        print("⚠️  No se recibió ningún diary para esa fecha.")
        print("   Prueba con una fecha más reciente o verifica que el usuario tiene calendario asignado.")
        return

    print("📄 Respuesta completa de Woffu:")
    print(json.dumps(diaries, indent=2, ensure_ascii=False))
    print("\n💡 Busca en la respuesta un campo que indique si el día es festivo/no laborable.")
    print("   Luego díselo a Claude para que actualice NON_WORKING_FIELDS en woffu.py.")


def cmd_clock(args):
    token, user_id = auth()

    if args.type == "in":
        dt      = apply_variation(ENTRY_HOUR, ENTRY_MIN, allow_before=False)
        label   = "ENTRADA"
        sign_in = True
    else:
        dt      = apply_variation(EXIT_HOUR, EXIT_MIN, allow_before=True)
        label   = "SALIDA"
        sign_in = False

    print(f"⏱  Fichando {label} a las {dt.strftime('%H:%M')}...")
    result = post_sign(token, user_id, dt, sign_in=sign_in)
    print(f"✅ {label} registrada: {dt.strftime('%Y-%m-%d %H:%M')} | {result}")


def cmd_backfill(args):
    """
    Rellena fichajes entre dos fechas saltando:
      • Fines de semana
      • Días ya fichados en Woffu
      • Ausencias/vacaciones registradas en Woffu
      • Festivos según el calendario de Woffu (vía Diaries)
    """
    token, user_id = auth()

    from_date = date.fromisoformat(args.from_date)
    to_date   = date.fromisoformat(args.to_date)

    if from_date > to_date:
        print("❌ La fecha de inicio es posterior a la de fin.")
        sys.exit(1)

    print("\n📋 Consultando fichajes existentes...")
    existing = get_existing_sign_dates(token, user_id, from_date, to_date)
    print(f"   → {len(existing)} días ya fichados")

    print("🏖️  Consultando ausencias y vacaciones...")
    try:
        absences = get_absence_dates(token, user_id, from_date, to_date)
        print(f"   → {len(absences)} días con ausencia registrada")
    except Exception as e:
        print(f"   ⚠️  No se pudieron obtener ausencias ({e})")
        absences = set()

    print("📅 Consultando calendario Woffu (diaries)...")
    non_working = set()
    try:
        diaries = get_diaries(token, user_id, from_date, to_date)
        # Mostramos estructura raw solo la primera vez (--verbose o primer backfill)
        non_working, detected_field = parse_non_working_days(diaries, verbose=args.verbose)
        if detected_field:
            print(f"   → Campo detectado: '{detected_field}' | {len(non_working)} días no laborables")
        else:
            print("   ⚠️  No se detectó campo de festivos en Diaries.")
            print("      Ejecuta: python woffu.py inspect --date <fecha_festivo>")
            print("      para ver la estructura y actualizar NON_WORKING_FIELDS en el script.")
    except Exception as e:
        print(f"   ⚠️  No se pudieron obtener diaries ({e})")

    tz      = pytz.timezone(TIMEZONE)
    current = from_date
    skipped = 0
    created = 0
    errors  = 0

    print("\n🗓️  Procesando días...\n")

    while current <= to_date:
        date_str = current.strftime("%Y-%m-%d")

        if not is_weekday(current):
            current += timedelta(days=1)
            continue

        if date_str in non_working:
            print(f"  🎉 {date_str} — festivo en calendario Woffu, saltado")
            skipped += 1
            current += timedelta(days=1)
            continue

        if date_str in absences:
            print(f"  🏖️  {date_str} — ausencia/vacaciones, saltado")
            skipped += 1
            current += timedelta(days=1)
            continue

        if date_str in existing:
            print(f"  ✅ {date_str} — ya fichado, saltado")
            skipped += 1
            current += timedelta(days=1)
            continue

        # Entrada: nunca antes de las 9:30
        entry_offset = random.randint(0, VARIATION_MINUTES)
        entry_dt = tz.localize(
            datetime(current.year, current.month, current.day, ENTRY_HOUR, ENTRY_MIN)
        ) + timedelta(minutes=entry_offset)

        # Salida: ±5 min
        exit_offset = random.randint(-VARIATION_MINUTES, VARIATION_MINUTES)
        exit_dt = tz.localize(
            datetime(current.year, current.month, current.day, EXIT_HOUR, EXIT_MIN)
        ) + timedelta(minutes=exit_offset)

        try:
            post_sign(token, user_id, entry_dt, sign_in=True)
            post_sign(token, user_id, exit_dt, sign_in=False)
            print(f"  🟢 {date_str} — entrada {entry_dt.strftime('%H:%M')} | salida {exit_dt.strftime('%H:%M')}")
            created += 1
        except Exception as e:
            print(f"  ❌ {date_str} — error: {e}")
            errors += 1

        current += timedelta(days=1)

    print(f"\n{'─'*50}")
    print(f"📊 Resumen:")
    print(f"   🟢 Creados:  {created} días fichados")
    print(f"   ⏭  Saltados: {skipped} días (ya fichados / festivos / ausencias)")
    print(f"   ❌ Errores:   {errors} días")
    print(f"{'─'*50}")


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Woffu Bot — gestión de fichajes")
    sub = parser.add_subparsers(dest="command", required=True)

    p_clock = sub.add_parser("clock", help="Fichar entrada o salida ahora")
    p_clock.add_argument("--type", choices=["in", "out"], required=True)

    p_back = sub.add_parser("backfill", help="Rellenar fichajes pasados")
    p_back.add_argument("--from", dest="from_date", required=True, help="Fecha inicio YYYY-MM-DD")
    p_back.add_argument("--to",   dest="to_date",   required=True, help="Fecha fin YYYY-MM-DD")
    p_back.add_argument("--verbose", action="store_true",
                        help="Muestra el JSON raw del primer diary (útil para depurar)")

    p_inspect = sub.add_parser("inspect", help="Ver diary raw de un día concreto")
    p_inspect.add_argument("--date", required=True, help="Fecha a inspeccionar YYYY-MM-DD")

    args = parser.parse_args()

    if args.command == "clock":
        cmd_clock(args)
    elif args.command == "backfill":
        cmd_backfill(args)
    elif args.command == "inspect":
        cmd_inspect(args)


if __name__ == "__main__":
    main()