"""Local development only: past working days of demo drivers, as if they had
shared live location all day. Fills the Trips page (Day 14) and route history
(Day 15) without a phone.

    python manage.py demo_drives            # the last 5 days, ending yesterday
    python manage.py demo_drives --days 3
    python manage.py demo_drives --offline  # no internet: simple L-shaped paths
    python manage.py demo_drives --remove   # delete what this command made

Who drives: active drivers whose name starts with "Demo", each with their
default vehicle (or a free active vehicle). A driver-day that overlaps one of
their real shifts is skipped. Each day: load at the warehouse, visit 3–4
client places, a lunch break with the phone silent, back to the warehouse.
The places are made as Geofences named "Demo · …".

Roads come from the public OSRM demo router (router.project-osrm.org, about
one request a second, coordinates of public places only). Without internet
the paths are straight lines with one corner.

Made shifts are recognisable: points but no live-location session (a real
phone always has one). --remove deletes exactly those, and the demo places.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import random
import time
import urllib.request

from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.audit import log
from apps.audit.models import AuditLog
from apps.fleet.models import Driver, Shift, Vehicle
from apps.tracking import track, trips
from apps.tracking.models import Geofence, LocationPoint

PREFIX = "Demo · "
WAREHOUSE = ("Ombor Sergeli", "Warehouse", 69.2210, 41.2265)
CLIENTS = [
    ("Chorsu bozori", 69.2346, 41.3265),
    ("Yunusobod mijoz", 69.2890, 41.3667),
    ("Chilonzor do'kon", 69.2034, 41.2756),
    ("Aeroport yuk terminali", 69.2700, 41.2600),
    ("Qo'yliq bozori", 69.3380, 41.2600),
    ("Olmazor ombori", 69.2050, 41.3450),
]
RADIUS_M = 300  # the router snaps ends to the nearest road
OSRM = ("https://router.project-osrm.org/route/v1/driving/"
        "{a[0]},{a[1]};{b[0]},{b[1]}?overview=full&geometries=geojson")
M_PER_DEG_LAT = 111_195


def _m_per_deg_lon(lat: float) -> float:
    return M_PER_DEG_LAT * math.cos(math.radians(lat))


class Roads:
    def __init__(self, offline: bool, warn):
        self.offline, self.warn, self.cache = offline, warn, {}

    def between(self, a, b) -> list[tuple[float, float]]:
        if (a, b) not in self.cache:
            self.cache[(a, b)] = self._fetch(a, b) or [a, (b[0], a[1]), b]
        return self.cache[(a, b)]

    def _fetch(self, a, b):
        if self.offline:
            return None
        try:
            req = urllib.request.Request(OSRM.format(a=a, b=b),
                                         headers={"User-Agent": "aktiv-fleet-demo/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                coords = json.load(r)["routes"][0]["geometry"]["coordinates"]
            time.sleep(1)  # the demo server asks for at most one request a second
            return [tuple(c) for c in coords]
        except Exception as e:  # noqa: BLE001 - any network trouble: fall back
            self.warn(f"No road from the router ({e}); using simple paths from now on.")
            self.offline = True
            return None


class Day:
    """Points of one simulated working day, in time order."""

    def __init__(self, rng: random.Random, at: dt.datetime, pos):
        self.rng, self.t, self.pos = rng, at, pos
        self.points: list[tuple[dt.datetime, float, float, float]] = []

    def _emit(self, lon, lat, accuracy=None):
        self.points.append((self.t, lon, lat, accuracy or round(self.rng.uniform(4, 15), 1)))

    def _near(self, lon, lat, meters=4):
        return (lon + self.rng.uniform(-meters, meters) / _m_per_deg_lon(lat),
                lat + self.rng.uniform(-meters, meters) / M_PER_DEG_LAT)

    def stand(self, minutes: float):
        end = self.t + dt.timedelta(minutes=minutes)
        while True:
            self.t += dt.timedelta(seconds=self.rng.uniform(30, 60))
            if self.t > end:
                self.t = end
                return
            self._emit(*self._near(*self.pos))

    def silent(self, minutes: float):
        """Phone in a pocket, vehicle parked: Telegram sends nothing."""
        self.t += dt.timedelta(minutes=minutes)

    def drive(self, path):
        steps = list(zip(path, path[1:], strict=False))
        legs = [track.distance_m(*a, *b) for a, b in steps]
        total, done = sum(legs), 0.0
        while done < total:
            seconds = self.rng.uniform(20, 40)
            kmh = 0 if self.rng.random() < 0.08 else self.rng.uniform(18, 55)  # lights, jams
            done = min(done + kmh / 3.6 * seconds, total)
            self.t += dt.timedelta(seconds=seconds)
            lon, lat = self._along(steps, legs, done)
            roll = self.rng.random()
            if roll < 0.01:  # a GPS jump (Day 10 leaves it out)
                self._emit(lon + 0.02, lat + 0.015)
                self.t += dt.timedelta(seconds=2)
            elif roll < 0.02:  # Telegram unsure
                self._emit(lon, lat, accuracy=250.0)
                continue
            self._emit(*self._near(lon, lat))
        self.pos = path[-1]

    @staticmethod
    def _along(steps, legs, meters):
        for (a, b), length in zip(steps, legs, strict=True):
            if meters <= length and length > 0:
                k = meters / length
                return a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k
            meters -= length
        return steps[-1][1]


class Command(BaseCommand):
    help = "Simulate past working days of demo drivers (local development only)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=5, help="Days back from yesterday")
        parser.add_argument("--offline", action="store_true", help="Do not ask the router")
        parser.add_argument("--remove", action="store_true", help="Delete the demo drives")

    def handle(self, *args, days=5, offline=False, remove=False, **options):
        if not settings.DEBUG:
            raise CommandError("Demo drives are for local development (DJANGO_DEBUG=1) only.")
        if remove:
            return self._remove()
        drivers = list(Driver.objects.filter(full_name__startswith="Demo", is_active=True)
                       .select_related("default_vehicle").order_by("full_name"))
        if not drivers:
            raise CommandError('No active driver whose name starts with "Demo".')
        places = self._places()
        roads = Roads(offline, lambda msg: self.stdout.write(self.style.WARNING(msg)))
        today = timezone.localdate()
        made = 0
        for back in range(days, 0, -1):
            day = today - dt.timedelta(days=back)
            used: set[int] = set()
            for driver in drivers:
                vehicle = self._vehicle(driver, day, used)
                if vehicle is None:
                    self.stdout.write(f"{day} {driver.full_name}: skipped (busy that day)")
                    continue
                used.add(vehicle.pk)
                shift = self._drive_day(driver, vehicle, day, places, roads)
                made += 1
                self.stdout.write(f"{day} {driver.full_name} · {vehicle.plate_display}: "
                                  f"{shift.points.count()} points, "
                                  f"{track.totals(shift).distance_km} km, "
                                  f"{shift.trips.count()} trips")
        self.stdout.write(self.style.SUCCESS(f"{made} demo days made. See /trips/."))

    # --- pieces ------------------------------------------------------------

    def _places(self):
        name, kind, lon, lat = WAREHOUSE
        all_ = [(name, kind, lon, lat)] + [(n, "Client", lo, la) for n, lo, la in CLIENTS]
        out = []
        for name, kind, lon, lat in all_:
            g, created = Geofence.objects.get_or_create(
                name=PREFIX + name,
                defaults=dict(kind=kind, address="Toshkent (demo)", radius_m=RADIUS_M,
                              center=Point(lon, lat, srid=4326)))
            if created:
                log.record(g, AuditLog.Action.CREATE, source=AuditLog.Source.SYSTEM,
                           reason="demo_drives")
            out.append((g.center.x, g.center.y))
        return out

    @staticmethod
    def _bounds(day: dt.date):
        tz = timezone.get_current_timezone()
        return (dt.datetime.combine(day, dt.time(7, 0), tzinfo=tz),
                dt.datetime.combine(day, dt.time(20, 0), tzinfo=tz))

    def _vehicle(self, driver, day, used) -> Vehicle | None:
        start, end = self._bounds(day)
        busy = Shift.objects.filter(started_at__lt=end).exclude(ended_at__lte=start)
        if busy.filter(driver=driver).exists():
            return None
        free = (Vehicle.objects.filter(is_active=True).exclude(pk__in=used)
                .exclude(pk__in=busy.values("vehicle")).order_by("plate"))
        dv = driver.default_vehicle
        if dv and free.filter(pk=dv.pk).exists():
            return dv
        return free.first()

    @transaction.atomic
    def _drive_day(self, driver, vehicle, day, places, roads) -> Shift:
        rng = random.Random(f"{driver.pk}-{day}")
        warehouse, clients = places[0], places[1:]
        start, _ = self._bounds(day)
        start += dt.timedelta(hours=1, minutes=rng.randint(0, 25))  # about 8:00
        sim = Day(rng, start, warehouse)
        sim._emit(*warehouse)
        sim.stand(rng.uniform(15, 35))  # loading
        stops = rng.sample(clients, rng.randint(3, 4))
        here = warehouse
        for n, place in enumerate(stops):
            sim.drive(roads.between(here, place))
            here = place
            if n == 1:
                sim.silent(rng.uniform(35, 50))  # lunch, phone quiet
            else:
                sim.stand(rng.uniform(10, 30))  # unloading
        sim.drive(roads.between(here, warehouse))
        sim.stand(rng.uniform(6, 12))

        first, last = sim.points[0][0], sim.points[-1][0]
        shift = Shift.objects.create(driver=driver, vehicle=vehicle,
                                     started_at=first - dt.timedelta(minutes=3),
                                     ended_at=last + dt.timedelta(minutes=2))
        LocationPoint.objects.bulk_create([
            LocationPoint(shift=shift, vehicle=vehicle, recorded_at=at, accuracy_m=acc,
                          point=Point(round(lon, 6), round(lat, 6), srid=4326))
            for at, lon, lat, acc in sim.points])
        track.recalculate(shift)  # Day 10: distance, speed, bad points
        trips.rebuild(shift)  # Day 14
        log.record(shift, AuditLog.Action.CREATE, source=AuditLog.Source.SYSTEM,
                   changes={"started_at": shift.started_at.isoformat(),
                            "ended_at": shift.ended_at.isoformat()},
                   reason="demo_drives")
        return shift

    @transaction.atomic
    def _remove(self):
        made = (Shift.objects.filter(driver__full_name__startswith="Demo",
                                     points__isnull=False, live_sessions__isnull=True)
                .distinct())
        n = 0
        for shift in made:
            log.record(shift, AuditLog.Action.DELETE, source=AuditLog.Source.SYSTEM,
                       reason="demo_drives --remove")
            shift.delete()
            n += 1
        places = Geofence.objects.filter(name__startswith=PREFIX)
        for g in places:
            log.record(g, AuditLog.Action.DELETE, source=AuditLog.Source.SYSTEM,
                       reason="demo_drives --remove")
        p = places.delete()[0]
        self.stdout.write(self.style.SUCCESS(f"Removed {n} demo days and {p} demo places."))
