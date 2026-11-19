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
docker compose exec web sh -c "python manage.py makemessages -l uz -l ru --no-obsolete --ignore=venv && python locale/translations.py && python manage.py compilemessages --ignore=venv"
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

## Shifts (Day 8)

A registered driver sends `/start_shift` in the bot and taps the vehicle they take. Their main vehicle comes first (⭐), then every active vehicle nobody is on shift with; with more than 8, they type part of the plate (e.g. `123`). `/end_shift` asks before ending. A vehicle has one driver at a time: if someone forgot `/end_shift`, the bot names them and says to call the dispatcher.

Managers see every shift on **Shifts** (`/shifts/`): filter by driver or plate, day, or "on shift now", and end a forgotten shift. The driver gets a message in the bot. Every start and end is in the audit log.

## Live location (Day 9)

After `/start_shift` the bot asks the driver to share **live** location (📎 → Location → Share My Live Location → Until I turn it off). Telegram then sends an update every few seconds; each is stored as a point of the open shift (PostGIS, `tracking_locationpoint`). One share is one `LiveSession`. The bot only speaks when something changes: sharing started, sharing stopped, a one-time location, or no shift. Points outside a shift are not stored; ending the shift ends the share.

The Shifts page shows whether each open shift is sharing, its number of points and a link to the last place on OpenStreetMap.

## Clean track (Day 10)

Each point gets the distance and speed from the last good point of the shift (`apps/tracking/track.py`). A point is **bad** (kept, but left out of distance, speed and alerts) when Telegram's accuracy is worse than 100 m, or when reaching it would need more than 150 km/h (a GPS jump). Moves under 15 m count as 0 (standing still). If the "jump" was right after all — the next point agrees with it — the track continues from there.

The Shifts page shows each shift's distance and top speed; the bot gives the distance when the shift ends. After changing the rules, or for points stored before Day 10:

```bash
docker compose exec web python manage.py recalculate_track
```

## Stop-sharing alerts (Day 11)

The bot checks every 30 seconds. When a driver on shift has had no location for **Company settings → stop alert minutes** (10), the managers' Telegram group gets an alert with the last known place, and the driver gets a reminder. When location comes back, the group hears that too. One alert per gap; gaps are stored (`SharingGap`) for reports.

To set up the group:
1. Create a Telegram group for the managers and add the bot to it. The bot says hello and remembers the group.
2. In the admin, open **Company settings** and choose it under **Alert group**.

## Live map (Day 12)

http://localhost:8001/map/ for directors and dispatchers. Every active vehicle is listed with a status, and shown on the map at its last good point (Day 10 bad points never move a marker):

- **Moving**: on shift, location coming, last point under 2 min old at 5 km/h or more.
- **Stopped**: on shift, location coming, otherwise.
- **No signal**: on shift, but not sharing, or no update for `stop_alert_minutes` (Company settings), as in the Day 11 watcher.
- **Off shift**: nobody on shift; shown at its last known place, if any.

The rules are in `apps/tracking/livemap.py`. The map is MapLibre GL 5.24 (vendored in `static/vendor/`) with the free OpenFreeMap style. Change `MAP_STYLE_URL` in `.env` to switch map source (e.g. self-hosted tiles). 
**Day 13:** the open page asks `/map/data/` for new positions every `MAP_REFRESH_SECONDS` (10). It pauses while the browser tab is hidden and catches up when you come back. The page itself never reloads. Pins glide smoothly from one position to the next over one refresh period, so vehicles appear to drive continuously (they trail the newest position by up to 10 s). A jump over 3 km, a hidden tab or the system's reduced-motion setting skips the glide. The list and counts update too. Clicking a vehicle opens a panel with driver, phone, speed, last update, shift start and distance on the shift. "Follow" keeps that vehicle in the middle of the map (dragging the map turns it off). A pin can only move as often as the driver's phone reports: Telegram sends live location every few seconds to a minute.

## Trips (Day 14)

http://localhost:8001/trips/ for directors and dispatchers. Each shift's clean track (Day 10) is cut into trips from A to B. A stop of 5 minutes or more ends one trip and starts the next:

- **Stayed:** every point for 5+ minutes is within 100 m of where the vehicle arrived.
- **Went quiet:** a phone standing still sends almost nothing. A 5+ minute gap covered slower than 5 km/h on average counts as a stop. A gap covered faster (sharing was off while driving) stays inside the trip.
- Moves under 200 m (around the yard) are not trips.

Trips are rebuilt from the points each time a point arrives and when the shift ends. Opening the page ends the trips of vehicles that have been silent for 5 minutes. The last trip of an open shift shows **On the way**. Ends of a trip are named after the company's places (Geofences from the template, circle or drawn area); otherwise coordinates linking to OpenStreetMap. Filter by driver/plate and day; the cards show the number of trips and kilometres for the filter. Trips are kept when retention deletes old points (Day 16). After changing the rules, `docker compose exec web python manage.py recalculate_track` rebuilds tracks and trips. Rules: `apps/tracking/trips.py`.

**Test trips without a phone:** `docker compose exec web python manage.py demo_drives` simulates the last 5 working days (ending yesterday) of the drivers whose name starts with "Demo": loading at a warehouse, 3–4 client places, a lunch with the phone silent, back. Roads come from the public OSRM demo router (`--offline` for simple paths). It also makes the places, named "Demo · …". Days that overlap a driver's real shift are skipped. `--days N` changes how many days; `--remove` deletes exactly what it made (shifts with points but no live session, and the demo places).

## Route history (Day 15)

http://localhost:8001/history/ for directors and dispatchers. Pick a vehicle, a day and how many days (1, 2, 3 or 7). It opens on the vehicle that drove last, on its last day with trips. The "Days with trips" chips jump to recent days. "On the map" on each Trips row opens that trip; "Route history" in the live map's vehicle panel opens that vehicle.

- The map shows the roads driven (good points only, Day 10). Each trip has its own colour, and stops are "P" markers.
- On the left: distance, trips and driving time, then the day as a list of trips and stops. Click a trip (in the list or on the map) to zoom to it and fade the others; click a stop to fly there.
- Playback: play/pause, 10×, 60× or 300×, and a slider to jump to any time. The clock shows Tashkent time and the speed at that moment. Nights between shifts are skipped.

Data: `apps/tracking/history.py`. Stops are found with the same rules as trips (Day 14).

## Admin panel

http://localhost:8000/admin/ for superusers (the demo director is one). Changes made there are written to the audit log; the audit log itself is read-only.

## Progress

- [x] Day 1 — kickoff: scope, roles, approval rules (`docs/day-01-kickoff.md`), data template + checker. Signed off.
- [x] Day 2 — local Docker Compose (PostGIS, Redis, Django, Tailwind), empty Django project with TailAdmin layout. Server + deploy postponed.
- [x] Day 3 — database design: 9 apps, PostGIS, rules enforced by DB constraints (`docs/day-03-database.md`). Approved.
- [x] Day 4 — login by role, role-based menu and access, Uzbek/Russian interface with language switch
- [x] Day 5 — admin panel; vehicle and driver lists; Excel import with preview (web + `import_fleet` command). Waiting for the company's filled template to load the real fleet.
- [x] Day 6 — bot skeleton (aiogram 3, polling locally / webhook on the server), /start, language choice (uz/ru), /language, /help. Tested with real Telegram.
- [x] Day 7 — registration by phone in the bot, managers confirm on New users; web sign-in confirmed in the bot (number matching), passwords for superusers only. Tested with real Telegram.
- [x] Day 8 — `/start_shift` with vehicle picker, `/end_shift`, Shifts page for managers (filters, end a forgotten shift). Tested with real Telegram.
- [x] Day 9 — live location from drivers on shift stored as points per shift; sharing status and points on the Shifts page. Tested with real Telegram.
- [x] Day 10 — distance and speed per point, bad points (accuracy >100 m, jumps >150 km/h) left out; distance on the Shifts page and in the bot. Committed.
- [x] Day 11 — stop-sharing detection (every 30 s); alert with last place to the managers' group, reminder to the driver, "back on" message
- [x] Day 12 — web live map (MapLibre + OpenFreeMap): vehicle list, statuses moving / stopped / no signal / off shift, filters and search
- [x] Day 13 — map updates every 10 s without reloading, pins glide smoothly; vehicle panel (driver, phone, speed, last update, shift distance) with Follow
- [x] Day 14 — trip detection (stop of 5+ min splits trips, parked silent phones count), Trips page: A → B with place names, time, km, top speed
- [x] Day 15 — route history: vehicle + day(s), roads and trips on the map, stops, playback (10×/60×/300×) with a time slider; links from Trips and the live map
