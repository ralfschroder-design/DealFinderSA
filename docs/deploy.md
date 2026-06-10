# Running DealFinderSA from git on a schedule

DealFinderSA is designed to run from git. All persistent state lives in Supabase and the
`.env` file; there is nothing local-only to preserve between runs.

---

## One-time setup on any host

```bash
git clone https://github.com/ralfschroder-design/DealFinderSA.git
cd DealFinderSA
python -m venv .venv

# Linux / macOS
source .venv/bin/activate
# Windows PowerShell
.\.venv\Scripts\Activate.ps1

pip install -e .
cp .env.example .env   # then edit .env
```

### Required environment variables (`.env`)

| Variable | Description |
|----------|-------------|
| `SUPABASE_URL` | Your project URL from Supabase → Settings → API |
| `SUPABASE_KEY` | The `service_role` key (full read/write; never expose publicly) |

### Optional — email alerts

| Variable | Description |
|----------|-------------|
| `SMTP_HOST` | Mail server, e.g. `smtp.gmail.com` |
| `SMTP_PORT` | Typically `587` (STARTTLS) |
| `SMTP_USER` | Sender address |
| `SMTP_PASS` | App password (Gmail recommended; Office 365 may be tenant-locked) |
| `ALERT_EMAIL_TO` | Recipient address for deal alerts |

Email is **optional** — if `SMTP_*` is not set, the alert step is skipped gracefully.

### Apply migrations (once per Supabase project)

```bash
python -m dealfinder.cli init-db
```

This prints SQL for migrations 001–004. Paste the output into the Supabase SQL editor.
Each migration is idempotent; they can be applied together in one go.

> **Migration 003/004 and SMTP are not required to start scraping.** Scoring and alert
> steps skip gracefully if the columns or credentials are not yet present.

---

## The scheduled command

```bash
python -m dealfinder.cli run-scrape
```

This single command runs the full pipeline in sequence:

1. **Scrape** — fetches Gumtree listings (cars / bikes / boats / jetskis)
2. **Score** — computes deal scores against the live market cohort (skipped if migration 003
   not applied)
3. **Alert** — emails any watches that match a new high-scoring listing (skipped if SMTP not
   configured)

Each step is isolated; a failure in one does not abort the others.

---

## Server deployment — Linux / cron (production)

The recommended production path is a Linux server with the repo checked out and a crontab
entry pointing at `scripts/run_scrape.sh`.

### Crontab example (twice daily at 06:00 and 18:00)

```cron
0 6,18 * * * /opt/DealFinderSA/scripts/run_scrape.sh >> /opt/DealFinderSA/scrape.log 2>&1
```

Replace `/opt/DealFinderSA` with the actual checkout path.

### Deploying a new version

```bash
cd /opt/DealFinderSA
git pull
# No restart needed — each cron run starts a fresh process
```

The venv is stable across updates; only run `pip install -e .` again if `pyproject.toml`
changes.

### `scripts/run_scrape.sh`

The wrapper script (`scripts/run_scrape.sh`) handles the `cd` to the repo root and invokes
the venv Python directly so no `activate` is needed and cron's minimal environment is not
an issue. Make it executable once:

```bash
chmod +x scripts/run_scrape.sh
```

---

## Windows — local testing

Use `scripts/register_scheduled_task.ps1` to register a Windows Scheduled Task for
**local testing only**. This is not the production path.

```powershell
# Register (runs daily at 07:00 by default)
.\scripts\register_scheduled_task.ps1

# Custom time
.\scripts\register_scheduled_task.ps1 -RunTime "08:30"

# Unregister
Unregister-ScheduledTask -TaskName "DealFinderSA-scrape" -Confirm:$false
```

The script is idempotent; running it again overwrites the existing task.

---

## Frequency and politeness

Once or twice a day is the right cadence for Gumtree. Running more frequently
confers no real benefit — new listings appear gradually — and risks being rate-limited or
blocked. The corpus value comes from **accumulation over weeks**, which naturally builds
denser cohorts and improves scoring quality, not from high polling frequency.
