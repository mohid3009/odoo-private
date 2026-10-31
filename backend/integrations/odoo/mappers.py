"""Local record -> Odoo `vals`. Field names are the Odoo 18 intended ones and UNVERIFIED against a live
instance (D-030): run `fields_get` on account.tax / product.product when Odoo is up and fix here only."""


def tax_vals(tax):
    return {
        "name": tax.name,
        "amount": float(tax.rate),
        "amount_type": "percent",
        "type_tax_use": "sale",
        "active": tax.is_active,
    }


def partner_vals(user):
    profile = getattr(user, "profile", None)
    return {
        "name": user.name or user.email,
        "email": user.email,
        "phone": (profile.phone if profile else "") or False,
        "street": (profile.address if profile else "") or False,
        "company_type": "company" if profile and profile.company_name else "person",
    }


def invoice_vals(invoice, partner_id, line_tax_ids):
    """account.move vals. `line_tax_ids` maps InvoiceLine.pk -> [Odoo tax ids]. Discount lines are negative price_unit."""
    return {
        "move_type": "out_invoice",
        "partner_id": partner_id,
        "invoice_date": str(invoice.invoice_date),
        "invoice_date_due": str(invoice.due_date),
        "ref": f"{invoice.subscription.number} {invoice.period_start}..{invoice.period_end}",
        "invoice_line_ids": [
            (0, 0, {
                "name": l.description,
                "quantity": l.quantity,
                "price_unit": float(l.unit_price),
                "tax_ids": [(6, 0, line_tax_ids.get(l.pk, []))],
            })
            for l in invoice.lines.all()
        ],
    }


def product_vals(product, odoo_tax_ids):
    return {
        "name": product.name,
        "list_price": float(product.sales_price),
        "standard_price": float(product.cost_price),
        "type": "service" if product.type in ("service", "software", "addon") else "consu",
        "taxes_id": [(6, 0, list(odoo_tax_ids))],
        "active": product.is_active,
        "description_sale": product.notes or False,
    }
