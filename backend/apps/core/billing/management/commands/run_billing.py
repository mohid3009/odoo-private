from datetime import date

from django.core.management.base import BaseCommand

from apps.core.billing.engine import run_billing


class Command(BaseCommand):
    help = "Bill every subscription period that is due (idempotent: running it twice creates nothing new)."

    def add_arguments(self, parser):
        parser.add_argument("--as-of", type=date.fromisoformat, help="billing date, YYYY-MM-DD (default: today)")

    def handle(self, *args, as_of=None, **options):
        run = run_billing(as_of)
        self.stdout.write(f"run #{run.pk} as of {run.as_of_date}: created={run.created_count} skipped={run.skipped_count} errors={run.error_count}")
        if run.log:
            self.stderr.write(run.log)
