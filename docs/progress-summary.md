# Aktivexpress Fleet: where we are (after Day 13, 19 Nov 2026)

A handoff note for the next chat. The plan is *Fleet App — Roadmap & Tech Stack.docx* (70 working days, in `~/Downloads`). The README has setup, commands and a section per day; this note is the short version plus the decisions and open items.

## The product

Fleet management for Aktivexpress (about 50 vehicles), later sold as SaaS to other logistics companies.

- **Drivers** use only the Telegram bot (@manfleetbot).
- **Directors, dispatchers and storekeepers** use the web app.
- **The Django admin** is for the super admin (the owner) only.

## Stack and decisions

- **Django 5.2:** server-rendered HTML with Tailwind, built on the free TailAdmin template. Alpine.js handles small UI behaviour. No React.
- **Data:** PostgreSQL with PostGIS, plus Redis.
- **Bot:** aiogram 3.32. It uses polling locally and a webhook later on the server.
- **Map:** MapLibre GL 5.24 (vendored in `static/vendor/`) with the OpenFreeMap style, which is free and needs no key. The map source can be switched with `MAP_STYLE_URL`.
- **Local only for now:** Docker Compose runs web, db, redis and tailwind, plus `tests` and `bot` under their own profiles. Server deploy comes later.
  - Docker web runs on port **8001**: `WEB_PORT=8001 docker compose up -d`.
  - The owner runs their own `manage.py runserver` on port 8000 from `backend/venv`.
- **Languages:** Uzbek (default) and Russian. Every string goes into `backend/locale/translations.py`, and a test fails if one is missing.
- **Sign-in:** through the Telegram bot (confirm the number shown in the browser). Passwords exist only for superusers, because email is rarely used in Uzbekistan.
- **Tests:** unit, functional and acceptance (Gherkin, pytest-bdd), every day. Run them with `docker compose --profile tests run --rm tests pytest -q`.
- **Data rules:** every change is written to the audit log, and the database enforces the rules with constraints.
- **Django admin:** kept as the plain default. An Unfold theme was tried and reverted. A proper super-admin console to manage client companies (tenants) is planned near the end. Keep a later multi-company setup in mind when designing models.

## Done, day by day

| Day | Delivered | Commit |
|---|---|---|
| 1–2 | Kickoff scope, roles and approval rules; Excel data template with checker; Docker stack; TailAdmin layout | cd028f8 |
| 3 | Database design: 9 apps, PostGIS, constraints | 974eafd |
| 4 | Sign-in by role, role menus, Uzbek/Russian with switch | 3d7e475 |
| 5 | Admin; vehicle and driver lists; Excel import with preview | d27d734 |
| 6 | Bot skeleton, /start, language choice | 82c6557 |
| 7 | Registration by phone in the bot; managers confirm; web sign-in confirmed in Telegram | b149e22 |
| 8 | `/start_shift` (vehicle picker, own vehicle first, busy vehicle refused), `/end_shift`, Shifts page | 7ba0624 |
| 9 | Telegram live location stored as points per shift | bac7182 |
| 10 | Clean track: distance and speed; bad points (accuracy > 100 m, > 150 km/h jumps) left out | d4e05dc |
| 11 | Stop-sharing alert after 10 min to the managers' group, reminder to the driver, "back on" message | c7e77ab |
| 12 | Live map `/map/`: list, statuses (moving, stopped, no signal, off shift), filters, search | ad7fa50 |
| 13 | Map updates every 10 s without reloading, pins glide smoothly; vehicle panel (driver, phone, speed, last update, shift distance) with Follow | 1bc4070 |

Days 7–11 were tested live with a real phone. Days 12–13 were checked in the browser with a simulated drive; a real-phone run is still to do.

## Open items

1. **Real data:** the owner shares the real vehicles and drivers by filling the Excel template in `backend/media/` (real data is never pasted in chat). Then: import (`/vehicles/import/`), drivers register in the bot, remove the demo data (vehicles 01 D 001–003 AA, "Demo Haydovchi Bir/Ikki", demo users), and run real tests to show the client.
2. **Alert group:** the manager adds @manfleetbot to their Telegram group, then the director chooses it in admin, *Company settings → Alert group*. Until then, alerts are only logged.
3. **Phone test of the live map:** start a shift in the bot, share live location, and watch `/map/` on a computer.
4. **The owner's Telegram** is linked to the demo driver "Demo Haydovchi Bir" for testing. Link it back to the director once real drivers exist.

## Next on the roadmap

- **Day 14:** trip detection. A stop over 5 minutes splits trips; a trips table shows A → B with km and time.
- **Day 15:** route history. Pick a vehicle and dates to see the roads driven, with playback.
- **Day 16:** retention of 1 or 3 months (Company settings), nightly cleanup.
- **Day 17:** test drive with 3 phones, fix bugs, demo (the tracking milestone).
- **Days 18–20:** approval engine, bot `/daily` with an odometer photo, photo storage (MinIO).

## Ways of working

- One roadmap day at a time. When a decision is the owner's, ask.
- Commit only when the owner asks; they sometimes commit themselves. Don't push. Commit messages end with the Co-Authored-By line.
- Never put secrets in chat. The bot token is in `backend/.env`, which is git-ignored.
- Use they/them for people.

## Gotchas learned

- The Tailwind watcher misses new template folders; run `docker compose restart tailwind`.
- aiogram's `Message.edit_date` is a Unix int, not a datetime. A Telegram "stop sharing" arrives as an edit without `live_period`.
- A Count/Sum annotation drops the model's `Meta.ordering`, so set `order_by` again.
- MapLibre's CSS sets `.maplibregl-map { position: relative }`: size the map div with `h-full w-full`, not `absolute`. Never set `className` on a marker's root element; style a child inside it.
- Browsers often lack Uzbek number and date data. Take the decimal comma and phrases like "1 daqiqa oldin" from Django.
- Tests that use "now" break just after midnight; use fixed times or patch `timezone.now`.
