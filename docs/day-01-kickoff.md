# Day 1 — Kickoff: scope, roles, approval rules

Status: **signed off by product owner 17.11.2026**
Date: 17.11.2026 · Source: *Fleet App — Roadmap & Tech Stack* (17.11.2026)

Day 1 is done when this page is signed off and the data template is sent to the company.

## 1. Scope of Version 1 (38 features)

| Area | # | Features | Phase / days |
|---|---|---|---|
| Tracking | 1–10 | Telegram live location, stop-sharing alert, route history (1–3 months), live map with status, trips A→B, geofences, speeding, long stop, after-hours movement, plan vs actual | 1 (6–17), 6 (51–52) |
| Daily data | 11–13 | Daily entry in bot with odometer photo, dispatcher confirms/rejects, reminder + missing-report list | 2 (18–25) |
| Fuel | 14–17 | Refill with 2 photos, dispatcher confirms, fuel log (Dizel, AI-80, AI-92, Metan, Propan), consumption vs norm | 3 (26–31) |
| Maintenance | 18–22 | Oil change with certificate photo, tire change with photo, reminders km-or-date, tires per wheel, repair history and cost/km | 4 (32–40) |
| Store | 23–27 | Stock with minimum levels, part request in bot → approve → hand over, director's stock view + low-stock alert, stock in with supplier/price/warranty, part → vehicle | 5 (41–48) |
| Drivers | 28–30 | Shift log, fines matched to driver on shift, driver score | 1 (8), 6 (53–54) |
| Documents | 31 | Expiry reminders: insurance, inspection, gas cylinder, licence, power of attorney | 6 (49–50) |
| General | 32–38 | Telegram alerts, Uzbek + Russian, 4 roles, Excel export, dashboard, audit log, photos attached to records | all |

**Not in Version 1:** ignition / idling, harsh braking, fuel-level sensor, exact odometer from tracker (need GPS hardware), mobile apps.
**Change rule:** new requests during the build go to a backlog after Day 70 unless they replace something.

## 2. Roles and what each can do

| Action | Director | Dispatcher | Storekeeper | Driver |
|---|:-:|:-:|:-:|:-:|
| Uses | Web | Web + Telegram | Web + Telegram | Telegram bot only |
| See live map, history, trips | ✓ | ✓ | — | — |
| See dashboard and all reports, Excel export | ✓ | ✓ | store only | — |
| Confirm / reject daily data, fuel, oil, tires | — ¹ | ✓ ² | — | — |
| Confirm part requests | — ¹ | ✓ ² | ✓ ² | — |
| Hand over a part (stock goes down) | — | — | ✓ | — |
| Add stock (purchases), edit catalogue | — | ✓ | ✓ | — |
| Edit vehicles, drivers, documents, geofences | ✓ | ✓ | — | — |
| Edit settings (norms, intervals, alert rules, retention) | ✓ | — | — | — |
| Manage users and roles; approve new bot users | ✓ | ✓ (drivers only) | — | — |
| Read audit log | ✓ | — | — | — |
| Start/end shift, share live location | — | — | — | ✓ |
| Send daily data, refuel, oil, tires, part request | — | — | — | ✓ (own vehicle on shift) |
| Receive Telegram alerts | ✓ (manager group) | ✓ | low stock | own reminders and results |

¹ The director *can* be added as an approver, but is not by default.
² Only the people marked in the template sheet *Who confirms what*.

**Mechanic:** the roadmap names "mechanic/storekeeper" as one role. Version 1 treats the mechanic as a Storekeeper who also sees the Maintenance page. → open question Q3.

## 3. Approval rules (one rule for all driver entries)

1. The driver submits in the bot, photos taken **in the bot at that moment**.
2. Automatic checks flag the entry before a dispatcher sees it.
3. A dispatcher marked for that type confirms or rejects (reason from a list: unclear photo, wrong numbers, not allowed, other + text).
4. The driver gets the result in the bot; a rejected entry is re-sent as a new entry.
5. **Only confirmed data counts** in reports, reminders, consumption and stock.
6. Every submit, confirm, reject and edit is written to the audit log (who, when, before/after).
7. A dispatcher may not confirm their own entry. A confirmed entry can be corrected only by the director, with a reason (audit-logged).
8. Pending over 2 hours → reminder to approvers; pending count shown on the dashboard.

| Entry | Driver sends | Required photos | Automatic flags | On confirm |
|---|---|---|---|---|
| Daily data | odometer, fuel/gas level, notes | odometer | odometer lower than last confirmed; jump > 1,000 km/day | odometer updates; service reminders recalculate |
| Refuel | fuel type, litres/m³, price, station | odometer before fueling + receipt | odometer lower than last; fuel type not used by vehicle; consumption > norm + 20% | enters fuel log; consumption vs norm calculated |
| Oil change | oil brand, odometer, service place | service certificate | odometer lower than last | oil reminder resets to next km/date |
| Tire change | positions, brand, size, odometer | certificate/receipt + tires | odometer lower than last | tire records per wheel; tire reminder resets |
| Part from store | item, quantity, vehicle, reason | old part (optional) | quantity > stock | storekeeper hands over → stock goes down, part linked to vehicle |

The 1,000 km/day and +20% thresholds are proposals → Q5.

## 4. Data templates (sent today)

`data-templates/fleet-data-template.xlsx` — one workbook, headers in Uzbek and Russian, dropdowns for fixed choices, an example row on each sheet. Sheets: Vehicles, Drivers, Last service, Service intervals, Documents, Store stock, Places (geofences), Who confirms what, Settings.

When the company sends it back we run:

```bash
docker compose run --rm tests python -m fleet_import check /data/filled.xlsx
```

It lists every problem by sheet, row and column. The same checks are the first step of the Day 5 import.

## 5. Open questions for sign-off

| # | Question | Proposed answer |
|---|---|---|
| Q1 | TailAdmin Pro or free? | **Decided:** free TailAdmin (MIT) |
| Q2 | Web app technology | **Decided:** Django templates, HTML + Tailwind CSS (no React) |
| Q3 | Is "mechanic" a separate role or the same person as the storekeeper? | Same role in V1 |
| Q4 | Can the director confirm entries? | Not by default, can be added per person |
| Q5 | Thresholds for automatic flags: odometer jump per day, consumption over norm | 1,000 km/day, +20% |
| Q6 | Vehicles on two fuels (e.g. AI-92 + Metan): separate norm for each? | Yes, the template has a second fuel + norm |
| Q7 | Retention of route history: 1 or 3 months? | 3 (template Settings sheet) |
| Q8 | Working days: Mon–Fri or Mon–Sat? | Template Settings sheet |
| Q9 | Who is in the manager alert group on Telegram? | Director + dispatchers |
| Q10 | Hosting provider and domain? Bot in @BotFather? | **Decided:** build locally for now; server later. Bot token needed by Day 6 |

## Sign-off

- [x] Product owner (Mirzokhid) — scope, roles, approval rules
- [ ] Manager — scope and change rule
- [ ] Data template sent to the company on ____
