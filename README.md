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

## 🌿 Branches

This repo has two branches depending on how you want to trigger the automatic clock-in/out:

| Branch | Trigger | Precision | Extra setup |
|---|---|---|---|
| `main` | [cron-job.org](https://cron-job.org) → webhook | ✅ Exact time, timezone-aware | Needs cron-job.org account + GitHub token |
| `github-cron` | GitHub's built-in scheduler | ⚠️ Can be 30+ min late | Nothing extra needed |

**Recommendation**: use `main` (cron-job.org) for reliable timing. Use `github-cron` if you want zero extra setup and don't mind occasional delays.

---

## 🚀 Setup

### 1. Create your repo from this template

Go to the template repo → click **"Use this template"** → **"Create a new repository"** → give it a name → set it as **Private** → click **"Create repository"**.

### 2. Add GitHub Secrets

Go to your repo → **Settings → Secrets and variables → Actions → New repository secret**

| Name | Value |
|---|---|
| `WOFFU_USER` | Your Woffu email |
| `WOFFU_PASS` | Your Woffu password |
| `WOFFU_DOMAIN` | Your company's Woffu domain (e.g. `mycompany.woffu.com`) |

### 3. Enable workflows

Go to the **Actions** tab in your repo and click **"I understand my workflows, enable them"**.

### 4. Activate the schedule

**If using `github-cron` branch**: make any small edit to activate GitHub's scheduler — no terminal needed:

1. Go to your repo → switch to the `github-cron` branch
2. Open any file (e.g. `README.md`) → click the ✏️ edit button
3. Make a tiny change (add a blank line at the end)
4. Click **"Commit changes"**

That's it — the schedule is now active. ✅

**If using `main` branch**: follow the cron-job.org setup below instead.

---

## 🗓️ Automatic daily schedule

### `main` branch — cron-job.org (recommended)

The workflow is triggered externally by [cron-job.org](https://cron-job.org) at the exact time you configure, with full timezone support (no UTC conversion needed).

Set up two jobs on cron-job.org:

| Job | Schedule (Europe/Madrid) | Body |
|---|---|---|
| Clock in | `25 9 * * 1-5` | `{"ref": "main", "inputs": {"type": "in", "dry_run": "false"}}` |
| Clock out | `25 18 * * 1-5` | `{"ref": "main", "inputs": {"type": "out", "dry_run": "false"}}` |

Each job hits this URL via POST:
```
https://api.github.com/repos/YOUR_USERNAME/auto_woffu/actions/workflows/woffu-clock.yml/dispatches
```

With these headers:
```
Authorization: Bearer YOUR_GITHUB_TOKEN
Accept: application/vnd.github.v3+json
Content-Type: application/json
```

You'll need a GitHub Personal Access Token (classic) with the `workflow` scope.

### `github-cron` branch — GitHub native scheduler

No extra setup needed. The workflow runs automatically on GitHub's scheduler every weekday:

| Action | UTC cron | Madrid time (winter) | Madrid time (summer) |
|---|---|---|---|
| Clock in | `25 8 * * 1-5` | ~9:25 | ~10:25 ⚠️ see note |
| Clock out | `25 17 * * 1-5` | ~18:25 | ~19:25 ⚠️ see note |

> **Summer time note**: GitHub Actions runs on UTC. In summer (CEST = UTC+2) update the crons in `.github/workflows/woffu-clock.yml`:
> - Clock in: `25 7 * * 1-5`
> - Clock out: `25 16 * * 1-5`

---

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

---

## 🔒 Security

- Credentials are **never stored in the code** — only in GitHub Secrets (encrypted)
- The script reads them from environment variables at runtime
- If you change your Woffu password, just update the `WOFFU_PASS` secret in GitHub
- Keep your cron-job.org GitHub token safe — treat it like a password