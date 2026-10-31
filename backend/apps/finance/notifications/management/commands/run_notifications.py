from datetime import date

from django.core.management.base import BaseCommand

from apps.finance.notifications.reminders import run_reminders


class Command(BaseCommand):
    help = "Send due-soon, overdue and expiring reminders (idempotent: reruns send nothing new)."

    def add_arguments(self, parser):
        parser.add_argument("--as-of", type=date.fromisoformat, help="YYYY-MM-DD (default: today)")

    def handle(self, *args, as_of=None, **options):
        r = run_reminders(as_of)
        self.stdout.write(f"reminders as of {r['as_of']}: due_soon={r['due_soon']} overdue={r['overdue']} expiring={r['expiring']}")
