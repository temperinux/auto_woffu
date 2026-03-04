# 🕐 Woffu Bot

Gestiona tus fichajes de Woffu automáticamente: rellena los del pasado y ficha cada día sin hacer nada.

---

## ✨ Funcionalidades

- **Backfill**: rellena fichajes pasados entre dos fechas (salta fines de semana y días ya fichados)
- **Auto-fichaje diario**: entrada a las 9:30 y salida a las 18:30 (±5 min de variación aleatoria, nunca antes de las 9:30)
- Corre en GitHub Actions — **no necesitas el PC encendido**

---

## 🚀 Instalación y configuración

### 1. Crea el repositorio en GitHub

1. Ve a [github.com/new](https://github.com/new)
2. Crea un repositorio **privado** (importante: privado para proteger tus credenciales)
3. Sube todos los archivos de esta carpeta

```bash
git init
git add .
git commit -m "Woffu bot inicial"
git remote add origin https://github.com/TU_USUARIO/woffu-bot.git
git push -u origin main
```

### 2. Añade los secretos en GitHub

En tu repositorio → **Settings → Secrets and variables → Actions → New repository secret**

| Nombre        | Valor                                      |
|---------------|--------------------------------------------|
| `WOFFU_USER`  | Tu email/usuario de Woffu                  |
| `WOFFU_PASS`  | Tu contraseña de Woffu                     |
| `WOFFU_DOMAIN`| `app.woffu.com` (o el subdominio de tu empresa) |

### 3. Activa los workflows

Ve a la pestaña **Actions** de tu repositorio y haz clic en "I understand my workflows, go ahead and enable them".

✅ A partir de aquí, fichará automáticamente cada día laborable.

---

## 🗂️ Rellenar fichajes pasados (backfill)

Instala las dependencias en tu ordenador:

```bash
pip install -r requirements.txt
```

Ejecuta el backfill indicando el rango de fechas:

```bash
# Exporta tus credenciales (solo para esta sesión de terminal)
export WOFFU_USER="tu@email.com"
export WOFFU_PASS="tucontraseña"
export WOFFU_DOMAIN="app.woffu.com"

# Rellena todos los días laborables entre esas fechas
python woffu.py backfill --from 2025-01-01 --to 2025-02-28
```

Si no exportas las variables, el script te pedirá usuario y contraseña interactivamente.

**El backfill:**
- ✅ Salta días ya fichados automáticamente
- ✅ Salta sábados y domingos
- ✅ Añade variación aleatoria en los horarios (no pone todos exactamente igual)
- ✅ Nunca ficha la entrada antes de las 9:30

---

## ⏱️ Fichar manualmente (cuando quieras)

```bash
python woffu.py clock --type in    # entrada
python woffu.py clock --type out   # salida
```

También puedes lanzarlo desde **GitHub Actions → Woffu Auto Fichaje → Run workflow** y elegir `in` o `out`.

---

## ⚙️ Ajustar horario

Si cambias de horario, edita estas líneas en `woffu.py`:

```python
ENTRY_HOUR, ENTRY_MIN = 9, 30   # hora entrada
EXIT_HOUR,  EXIT_MIN  = 18, 30  # hora salida
VARIATION_MINUTES = 5            # variación ±minutos
```

Y actualiza los cron en `.github/workflows/woffu-clock.yml` acordemente (recuerda que GitHub Actions usa **UTC**).

---

## 🔒 Seguridad

- Las credenciales **nunca se guardan en el código**, solo en los Secrets de GitHub (cifrados)
- Mantén el repositorio en **privado**
- Si cambias la contraseña de Woffu, actualiza el secret `WOFFU_PASS`

---

## 🗓️ Crons configurados

| Acción   | Cron UTC     | Hora Madrid (invierno) | Hora Madrid (verano) |
|----------|--------------|------------------------|----------------------|
| Entrada  | `25 8 * * 1-5`  | ~9:25 → script llega a ~9:30 ±5 | ~10:25 ⚠️ ver nota |
| Salida   | `25 17 * * 1-5` | ~18:25 → script llega a ~18:30 ±5 | ~19:25 ⚠️ ver nota |

> **Nota horario de verano**: GitHub Actions usa UTC fijo. En verano (CEST = UTC+2) los fichajes se harán ~1h más tarde. Si quieres máxima precisión en verano, actualiza los crons entre marzo y octubre:
> - Entrada verano: `25 7 * * 1-5`
> - Salida verano: `25 16 * * 1-5`
