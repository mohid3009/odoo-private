from django.core.management.base import BaseCommand

from apps.finance.notifications.services import send_pending


class Command(BaseCommand):
    help = "Send queued messages and retry failed ones that are due (max 3 attempts; backoff 1, 5, 30 min)."

    def handle(self, *args, **options):
        self.stdout.write(f"attempted {send_pending()} message(s)")
