# Aktivexpress Fleet

Web app + Telegram bot for the 50-vehicle fleet. Plan: *Fleet App — Roadmap & Tech Stack* (70 working days).

**Stack:** Django (server-rendered HTML + Tailwind CSS, based on the free [TailAdmin](https://github.com/TailAdmin/tailadmin-free-tailwind-dashboard-template) template, MIT) · PostgreSQL + PostGIS · Redis · Alpine.js for small UI behaviour. Built and run locally with Docker Compose; server deploy comes later.

| Path | What |
|---|---|
| `backend/config/` | Django settings and URLs (all machine-specific values come from `.env`) |
| `backend/apps/core/` | Layout, sidebar menu, dashboard, `/health/`, company settings |
| `backend/apps/{accounts,fleet,tracking,entries,store,maintenance,documents,audit}/` | Data model (Day 3) |
| `backend/templates/` | Base layout and partials (sidebar, header, breadcrumb, icons) |
| `backend/theme/` | Tailwind build: `tailadmin.css` (upstream, unchanged) + `app.css` (ours) → `static/css/app.css` |
| `backend/fleet_import/` | Company data template and checker (Day 1; Day 5 import uses it) |
| `docs/` | Decisions per roadmap day |
| `data-templates/` | Excel template for the company; filled copies are git-ignored |

## Run locally

```bash
cp .env.example .env
```

```bash
docker compose up -d
```

Open http://localhost:8000. `tailwind` rebuilds the CSS whenever a template changes. It does not notice a newly created template folder: after adding one, run `docker compose restart tailwind`.

Running `manage.py runserver` on your machine instead? Postgres (5432) and Redis (6379) are published on 127.0.0.1, so set `POSTGRES_HOST=localhost` and `REDIS_URL=redis://localhost:6379/0` in `backend/.env`. To run both at once, start the Docker one on another port: `WEB_PORT=8001 docker compose up -d`.

```bash
docker compose exec web python manage.py createsuperuser
```

To try each role locally (director, dispatcher, storekeeper, driver), create demo users. It prints one password for all of them; it refuses to run unless `DJANGO_DEBUG=1`. Since Day 7 only superusers (the demo director) can use the password; everyone else signs in with Telegram (below).

```bash
docker compose exec web python manage.py create_demo_users
```

## Translations (Uzbek / Russian)

Our own UI strings are translated in `backend/locale/translations.py`. After adding or changing text:

```bash
docker compose exec web sh -c "python manage.py makemessages -l uz -l ru --no-obsolete && python locale/translations.py && python manage.py compilemessages"
```

A test fails while any string is untranslated.

## Tests

Three levels, all in `backend/tests/`, run against real PostGIS and Redis:

- `unit/` — one function at a time
- `functional/` — a module or page through its public API
- `acceptance/` — business scenarios in Gherkin (`features/*.feature`), tagged by roadmap day

```bash
docker compose --profile tests run --rm tests
```

```bash
docker compose --profile tests run --rm tests pytest -m acceptance
```

## Company data template

```bash
docker compose --profile tests run --rm tests python -m fleet_import check /data/filled.xlsx
```

## Importing vehicles and drivers

Directors and dispatchers: **Vehicles → Import from Excel**. Upload the filled template, check the preview (new / changed / unchanged rows, or every problem by sheet, row and column), then confirm. Nothing is saved before the confirm, and a file with any problem imports nothing. Rows are matched by plate and Telegram phone, so a corrected file can be imported again; nothing is ever deleted. Every created or changed row is written to the audit log.

The same from the command line (the file must be inside `backend/`, e.g. `backend/media/`):

```bash
docker compose exec web python manage.py import_fleet media/filled.xlsx --dry-run
```

## Telegram bot

1. Create the company bot with @BotFather and copy its token.
2. Put it in `.env` as `TELEGRAM_BOT_TOKEN=...` (never in git or chat).
3. Start it. Locally it polls Telegram, so no public URL is needed:

```bash
docker compose --profile bot up -d bot
```

```bash
docker compose logs -f bot
```

On the server it runs in webhook mode: set `BOT_MODE=webhook`, `BOT_WEBHOOK_URL=https://<domain>/bot/webhook` and a long random `BOT_WEBHOOK_SECRET`; the reverse proxy forwards `/bot/` to the bot container on port 8080. Telegram updates without the secret are refused.

Running Django from `backend/venv` on your machine? Install the new requirements there too: `pip install -r backend/requirements.txt`, then `python manage.py migrate`.

## Sign-in and registration (Day 7)

Staff sign in with **Telegram orqali kirish**: the page shows a number and a link/QR code to the bot; the person taps the same number in the bot and the browser signs in. The link works once, for 3 minutes. Passwords work only for superusers (a backup for when Telegram is unavailable).

Before that, a person registers once: `/start` in the bot → pick the language → **Send my phone number**. The number must match a staff user (`phone` in the admin) or a driver. A manager confirms on **New users**: dispatchers confirm drivers, the director confirms staff. The bot tells the person the result.

To link yourself locally: sign in as the demo director (password), put your Telegram phone number on a staff user in the admin, share your number in the bot, then confirm yourself on **New users**.

## Admin panel

http://localhost:8000/admin/ for superusers (the demo director is one). Changes made there are written to the audit log; the audit log itself is read-only.

## Progress

- [x] Day 1 — kickoff: scope, roles, approval rules (`docs/day-01-kickoff.md`), data template + checker. Signed off.
- [x] Day 2 — local Docker Compose (PostGIS, Redis, Django, Tailwind), empty Django project with TailAdmin layout. Server + deploy postponed.
- [x] Day 3 — database design: 9 apps, PostGIS, rules enforced by DB constraints (`docs/day-03-database.md`). Approved.
- [x] Day 4 — login by role, role-based menu and access, Uzbek/Russian interface with language switch
- [x] Day 5 — admin panel; vehicle and driver lists; Excel import with preview (web + `import_fleet` command). Waiting for the company's filled template to load the real fleet.
- [x] Day 6 — bot skeleton (aiogram 3, polling locally / webhook on the server), /start, language choice (uz/ru), /language, /help. Tested with real Telegram.
- [x] Day 7 — registration by phone in the bot, managers confirm on New users; web sign-in confirmed in the bot (number matching), passwords for superusers only
