from django.core.management.base import BaseCommand

from integrations.odoo import sync


class Command(BaseCommand):
    help = "Retry every Odoo mirror that is 'pending' or 'error' (taxes, products, invoices)."

    def handle(self, *args, **options):
        sync.sync_pending()
        self.stdout.write("sync_odoo done")
