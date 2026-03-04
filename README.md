# 🕐 auto_woffu

Automates your Woffu clock-ins and clock-outs. Fill in past missing days and let it clock you in and out every day automatically — no PC needed.

---

## ✨ Features

- **Daily auto clock-in/out** via GitHub Actions — runs in the cloud, no PC required
- **Backfill** past missing days between two dates
- Automatically skips weekends, public holidays and registered absences (pulled directly from Woffu)
- Random time variation so signs don't look robotic (entry: 9:20–9:30, exit: 18:25–18:35)
- Dry run mode to test without actually clocking

---

## 🚀 Setup

### 1. Fork or clone this repo

```bash
git clone https://github.com/YOUR_USERNAME/auto_woffu.git
cd auto_woffu
```

### 2. Add GitHub Secrets

Go to your repo → **Settings → Secrets and variables → Actions → New repository secret**

| Name | Value |
|---|---|
| `WOFFU_USER` | Your Woffu email |
| `WOFFU_PASS` | Your Woffu password |
| `WOFFU_DOMAIN` | Your company's Woffu domain (e.g. `mycompany.woffu.com`) |

### 3. Enable workflows

Go to the **Actions** tab in your repo and click **"I understand my workflows, enable them"**.

That's it — it will clock you in and out automatically every working day. ✅

---

## 🗓️ Automatic daily schedule

Two workflows run on a cron schedule every weekday (Mon–Fri):

| Action | UTC cron | Madrid time (winter) | Madrid time (summer) |
|---|---|---|---|
| Clock in | `25 8 * * 1-5` | ~9:25 | ~10:25 ⚠️ see note |
| Clock out | `25 17 * * 1-5` | ~18:25 | ~19:25 ⚠️ see note |

> **Summer time note**: GitHub Actions runs on UTC. In summer (CEST = UTC+2) the schedule shifts 1 hour later. Update the crons in `.github/workflows/woffu-clock.yml` between March and October:
> - Clock in: `25 7 * * 1-5`
> - Clock out: `25 16 * * 1-5`

Before each sign, the script checks your Woffu diary and skips automatically if:
- 📅 It's a weekend
- 🎉 It's a public holiday
- 🏖️ You have a registered absence or vacation

---

## 🗂️ Backfill past days

### Option A — via GitHub Actions (no PC needed)

Go to **Actions → Woffu Backfill → Run workflow**, fill in the date range and run.

Set `dry_run = true` first to preview what would be clocked before committing.

### Option B — locally

```bash
pip install -r requirements.txt

export WOFFU_USER="you@company.com"
export WOFFU_PASS="yourpassword"
export WOFFU_DOMAIN="mycompany.woffu.com"

# Preview first
python woffu.py backfill --from 2025-01-01 --to 2025-03-01 --dry-run

# Run for real
python woffu.py backfill --from 2025-01-01 --to 2025-03-01
```

The backfill automatically skips:
- ✅ Days already clocked
- ✅ Weekends
- ✅ Public holidays (from your Woffu calendar)
- ✅ Registered absences and vacation days

---

## ⏱️ Manual clock-in/out

### Via GitHub Actions

Go to **Actions → Woffu Auto Clock → Run workflow**, choose `in` or `out`.

### Locally

```bash
python woffu.py clock --type in
python woffu.py clock --type out

# Dry run (no actual clocking)
python woffu.py clock --type in --dry-run
```

---

## ⚙️ Adjusting your schedule

Edit these lines in `woffu.py`:

```python
ENTRY_HOUR, ENTRY_MIN = 9, 30    # target entry time
EXIT_HOUR,  EXIT_MIN  = 18, 30   # target exit time
VARIATION_MINUTES = 5             # random variation in minutes
```

Then update the crons in `.github/workflows/woffu-clock.yml` accordingly (remember GitHub Actions uses **UTC**).

---

## 🔒 Security

- Credentials are **never stored in the code** — only in GitHub Secrets (encrypted)
- The script reads them from environment variables at runtime
- If you change your Woffu password, just update the `WOFFU_PASS` secret in GitHub
