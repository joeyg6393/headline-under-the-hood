# Deploying to Render

This project is configured for a **quick-path** deploy: a single Render Web
Service backed by a 1 GB persistent disk that stores both the SQLite database
and the raw release-text files. Temporal is disabled so analysis runs
synchronously inside each request.

If you outgrow this (more traffic, want zero-downtime DB upgrades, or want
fanned-out workers), migrate to Postgres + Temporal Cloud + a Background
Worker. The `app/` code is already structured for that swap.

## Prerequisites

1. A [Render](https://dashboard.render.com/register) account
2. A [Google AI Studio API key](https://aistudio.google.com/apikey) for Gemini
3. This repo pushed to GitHub (Render reads code from GitHub)

## One-time setup

### 1. Push this repo to GitHub

Create an empty private repository at https://github.com/new — call it
`headline-under-the-hood` or whatever you like. **Do not initialize it** with
a README, license, or `.gitignore`; this project already has them.

From the project folder:

```powershell
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

If `git push` asks for credentials, GitHub will direct you to a browser-based
sign-in. Use a personal access token or the GitHub CLI (`gh auth login`) if
the password method fails.

### 2. Deploy via Blueprint

Render reads `render.yaml` at the repo root and provisions everything in one
go.

1. Sign in to Render and go to https://dashboard.render.com/blueprints
2. Click **New Blueprint Instance**
3. Connect your GitHub account (if not already) and pick the repo
4. Render will detect `render.yaml` and show what it's about to create:
   one Web Service named `headline-under-the-hood`, with a 1 GB persistent
   disk attached
5. It will prompt you for the **GEMINI_API_KEY** value (because `render.yaml`
   marks it `sync: false`). Paste the key from Google AI Studio
6. Click **Apply**

The first deploy takes 3–5 minutes (downloads Python, installs dependencies,
runs the start command, attaches the disk). Watch progress in the **Logs** tab.

### 3. Confirm it's live

Render will give you a URL like `https://headline-under-the-hood.onrender.com`.

- Open it in a browser. The dashboard loads but the feed is empty.
- Click **⋯** (top-right) → **Seed examples** to load the 14 demo releases.
- Click any card to inspect it, or click **View full analysis** for the deep
  dive with claims table, composition bar, revision watch, tone, and Bayesian
  probability sections.

## Day-to-day workflow

| What you want to do                       | How                                                                        |
| ----------------------------------------- | -------------------------------------------------------------------------- |
| Deploy a code change                       | `git push` to `main` — Render auto-deploys                                |
| Roll back a bad deploy                     | Render Dashboard → service → Deploys tab → "Roll back to this deploy"      |
| Read logs                                  | Dashboard → service → Logs tab                                             |
| Rotate the Gemini key                      | Dashboard → service → Environment tab → edit `GEMINI_API_KEY` → "Save"     |
| Add a custom domain                        | Dashboard → service → Settings → Custom Domains                            |
| Scale up (more RAM/CPU)                    | Dashboard → service → Settings → Instance Type                             |
| Resize the disk                            | Dashboard → service → Disks → app-data → "Resize" (uptime-preserving)      |
| Inspect the database from your laptop      | Dashboard → service → Shell tab → `sqlite3 /var/data/app.db`              |

## Environment variables (reference)

These are set automatically by `render.yaml`:

| Key             | Value                              | Why                                                            |
| --------------- | ---------------------------------- | -------------------------------------------------------------- |
| `PYTHON_VERSION`| `3.11.9`                           | Pin to a known-good runtime                                    |
| `APP_NAME`      | `Headline Under The Hood`          | Display name                                                   |
| `DATABASE_PATH` | `/var/data/app.db`                 | SQLite file lives on the persistent disk                       |
| `STORAGE_ROOT`  | `/var/data/storage`                | Raw release text lives on the persistent disk                  |
| `USE_TEMPORAL`  | `false`                            | Synchronous analysis path; no worker required                  |
| `GEMINI_MODEL`  | `gemini-2.5-flash-lite`            | Fastest/cheapest Gemini model                                  |

Set by you when prompted:

| Key              | Where to get it                                                |
| ---------------- | -------------------------------------------------------------- |
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey                             |

## Costs

- **Web service (Starter)** — $7/mo, always-on, 512 MB RAM, 0.5 CPU
- **Persistent disk** — $0.25/GB/mo → $0.25/mo for 1 GB
- **Gemini API** — Free tier covers the analyzer for low traffic
- **Total** — about **$7.25/mo** with the recommended Starter plan

To experiment for free, change `plan: starter` to `plan: free` in
`render.yaml`. The free tier sleeps after 15 minutes of inactivity, so the
first request after idle has a ~30-second cold start.

## Future: migrating to Postgres + Temporal Cloud

When you're ready:

1. Provision a Render Postgres database (Basic-256mb is $6/mo)
2. Add `psycopg[binary]` to `requirements.txt`
3. Rewrite `app/db.py` to read `DATABASE_URL` instead of `DATABASE_PATH`
4. Add a Background Worker service in `render.yaml` running `python -m app.worker`
5. Sign up for [Temporal Cloud](https://cloud.temporal.io), grab the namespace + API key
6. Set `USE_TEMPORAL=true`, `TEMPORAL_ADDRESS`, `TEMPORAL_API_KEY` in env vars
7. `git push` — Render handles the rest

The persistent disk can be removed at that point since both data sources move
off-disk.

## Troubleshooting

**Build fails with "could not find a version that satisfies the requirement…"**
Mismatch between the pinned `PYTHON_VERSION` and a package that requires a
newer Python. Bump `PYTHON_VERSION` in `render.yaml`.

**"Service Unavailable" right after deploy**
Render is still attaching the disk and waiting for the healthcheck to pass.
Give it 60 seconds; check Logs if it persists.

**Reports show as "Pending" forever**
With `USE_TEMPORAL=false` this shouldn't happen — analysis is synchronous.
If you see it, the analyzer raised an exception; check Logs for a traceback.

**Database "locked" errors under load**
SQLite + WAL handles modest concurrency, but if you're seeing this regularly
it's the signal to migrate to Postgres. See the section above.
