"""Assess stored points again: after the rules change, or for points saved before Day 10."""

from django.core.management.base import BaseCommand

from apps.fleet.models import Shift
from apps.tracking import track


class Command(BaseCommand):
    help = "Recalculate distance, speed and bad points of shifts' tracks."

    def add_arguments(self, parser):
        parser.add_argument("--shift", type=int, action="append",
                            help="Shift id (repeatable). Default: every shift with points.")

    def handle(self, *args, shift=None, **options):
        shifts = Shift.objects.filter(points__isnull=False).distinct().order_by("pk")
        if shift:
            shifts = shifts.filter(pk__in=shift)
        for sh in shifts:
            changed = track.recalculate(sh)
            t = track.totals(sh)
            self.stdout.write(f"shift {sh.pk}: {t.points} points, {t.bad_points} bad, "
                              f"{t.distance_km} km, {changed} changed")
