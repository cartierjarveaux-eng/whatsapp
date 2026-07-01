# Rica Pro — WhatsApp CRM & 20hr Scheduler

Live CRM for Rica Pro WhatsApp Business (+57 301 6880127)

## Live App
**https://cartierjarveaux-eng.github.io/rica-pro/**

## Files
- `index.html` — Live CRM web app
- `scheduler.py` — 20hr auto-scheduler (runs via GitHub Actions)
- `contacts_state.json` — Contact database with window tracking
- `.github/workflows/scheduler.yml` — Runs scheduler every hour, free

## Setup GitHub Secrets
Go to: Settings → Secrets and variables → Actions → New repository secret

| Secret name | Value |
|---|---|
| `WA_TOKEN` | Your Meta access token |
| `WA_PHONE_NUMBER_ID` | `119440352708700` |

## How it works
1. Scheduler runs every hour via GitHub Actions (free)
2. Checks which contacts are 20hrs since last message
3. Sends free text if within 24hr window
4. Sends paid template ($0.0125) if window expired
5. After 3 no-replies, moves contact to cold list
6. Updates contacts_state.json automatically
