"""python manage.py import_fleet filled.xlsx [--dry-run]"""

from django.core.management.base import BaseCommand, CommandError

from apps.fleet.importer import ImportBlocked, apply_import, plan_import


class Command(BaseCommand):
    help = "Import vehicles and drivers from the filled company data template."

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--dry-run", action="store_true",
                            help="Check and show what would change; write nothing.")

    def handle(self, path, dry_run, **options):
        if dry_run:
            plan = plan_import(path)
            self.stdout.write(plan.summary())
            if not plan.ok:
                raise CommandError("the file has problems")
            return
        try:
            plan = apply_import(path)
        except ImportBlocked as exc:
            self.stdout.write(exc.args[0].summary())
            raise CommandError("nothing imported") from exc
        self.stdout.write(self.style.SUCCESS("Imported. " + plan.summary()))
