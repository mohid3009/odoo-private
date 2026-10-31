"""Mirror local records into Odoo. Every function swallows Odoo failures into `odoo_sync_status` (rule 7):
skipped = ODOO_ENABLED off | pending = Odoo unreachable (retry later) | synced | error = Odoo rejected (see odoo_error)."""
import logging

from django.conf import settings

from . import mappers
from .client import OdooError, OdooUnavailable, get_client

log = logging.getLogger(__name__)


def _record(model, pk, status, error="", **extra):
    model.objects.filter(pk=pk).update(odoo_sync_status=status, odoo_error=error[:2000], **extra)


def _mirror(model, pk, work):
    """Run work(obj, client) -> dict of extra fields (e.g. the Odoo id) and store the outcome."""
    obj = model.objects.filter(pk=pk).first()
    if obj is None:
        return
    if not settings.ODOO_ENABLED:
        return _record(model, pk, "skipped")
    try:
        extra = work(obj, get_client()) or {}
    except OdooUnavailable as e:
        return _record(model, pk, "pending", str(e))
    except OdooError as e:
        return _record(model, pk, "error", str(e))
    except Exception as e:  # never let a mapping bug break a save
        log.exception("odoo sync crashed for %s pk=%s", model.__name__, pk)
        return _record(model, pk, "error", f"{type(e).__name__}: {e}")
    _record(model, pk, "synced", **extra)


def _upsert(client, odoo_model, odoo_id, domain, vals):
    """Create or update; reuse an existing Odoo row that matches `domain` instead of duplicating it."""
    if not odoo_id:
        found = client.search_read(odoo_model, domain, ["id"], limit=1)
        odoo_id = found[0]["id"] if found else None
    if odoo_id:
        client.write(odoo_model, [odoo_id], vals)
        return odoo_id
    return client.create(odoo_model, vals)


def _push_tax(tax, client):
    domain = [("name", "=", tax.name), ("type_tax_use", "=", "sale")]
    return _upsert(client, "account.tax", tax.odoo_tax_id, domain, mappers.tax_vals(tax))


def sync_tax(pk):
    from apps.core.catalog.models import Tax

    _mirror(Tax, pk, lambda tax, c: {"odoo_tax_id": _push_tax(tax, c)})


def sync_product(pk):
    from apps.core.catalog.models import Product

    def work(product, client):
        tax_ids = []
        for tax in product.taxes.all():  # a product can only reference taxes that exist in Odoo
            if not tax.odoo_tax_id:
                tax.odoo_tax_id = _push_tax(tax, client)
                _record(type(tax), tax.pk, "synced", odoo_tax_id=tax.odoo_tax_id)
            tax_ids.append(tax.odoo_tax_id)
        domain = [("name", "=", product.name)]
        oid = _upsert(client, "product.product", product.odoo_product_id, domain, mappers.product_vals(product, tax_ids))
        return {"odoo_product_id": oid}

    _mirror(Product, pk, work)


def sync_pending():
    """Retry everything not yet synced (used by the `sync_odoo` command in Phase 4)."""
    from apps.core.catalog.models import Product, Tax

    for pk in Tax.objects.filter(odoo_sync_status__in=["pending", "error"]).values_list("pk", flat=True):
        sync_tax(pk)
    for pk in Product.objects.filter(odoo_sync_status__in=["pending", "error"]).values_list("pk", flat=True):
        sync_product(pk)
