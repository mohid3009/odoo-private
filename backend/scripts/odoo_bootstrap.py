"""One-time Odoo setup after `odoo -i base,contacts,account,sale_management`: India/INR + chart of accounts (D-018).

Run from backend/ (or in the web container):  python scripts/odoo_bootstrap.py
UNVERIFIED against a live instance (Phase 0 gate pending, D-030): check model/field names with fields_get if a call faults.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from integrations.odoo.client import get_client  # noqa: E402

c = get_client()

company = c.search_read("res.company", [], ["name", "country_id", "currency_id"], limit=1)[0]
india = c.search_read("res.country", [("code", "=", "IN")], ["id"], limit=1)[0]["id"]
inr = c.execute("res.currency", "search", [("name", "=", "INR"), ("active", "in", [True, False])], limit=1)[0]
c.write("res.currency", [inr], {"active": True})
c.write("res.company", [company["id"]], {"country_id": india, "currency_id": inr})
print("company set to India / INR:", company["id"])

# country must be set BEFORE l10n_in so the chart of accounts loads for this company
mod = c.search_read("ir.module.module", [("name", "=", "l10n_in")], ["state"], limit=1)[0]
if mod["state"] != "installed":
    c.execute("ir.module.module", "button_immediate_install", [mod["id"]])
print("l10n_in:", c.search_read("ir.module.module", [("name", "=", "l10n_in")], ["state"], limit=1)[0]["state"])

# Odoo refuses to post an invoice (account.move.action_post) until the company has a full address incl. a state (l10n_in).
# Found by the first live run, not by the fake Odoo. Only fills blanks, so a real address already set is never overwritten.
co = c.search_read("res.company", [("id", "=", company["id"])], ["street", "city", "zip", "state_id"], limit=1)[0]
state = c.search_read("res.country.state", [("country_id", "=", india), ("code", "=", "KL")], ["id"], limit=1)
blank = {k: v for k, v in {"street": "Demo Street 1", "city": "Kochi", "zip": "682001", "state_id": state[0]["id"] if state else False}.items() if not co[k]}
if blank:
    c.write("res.company", [company["id"]], blank)
print("company address filled:", sorted(blank) or "already complete")

journals = c.search_read("account.journal", [("type", "=", "sale")], ["name", "code"])
print("sales journals:", journals)
if not journals:
    sys.exit("No sales journal: chart of accounts did not load. Load it from Odoo UI (Accounting > Configuration) and re-run.")
