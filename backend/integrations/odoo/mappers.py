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
