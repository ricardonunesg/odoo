from odoo.addons.primavera_connector.models.primavera_connection import PrimaveraConnection
import re
c = env["primavera.connection"].browse(1)
P = env["res.partner"].sudo().with_context(active_test=False)
def ficticio(vat):
    v = re.sub(r"[^A-Z0-9]", "", (vat or "").upper())
    if len(v) > 2 and v[:2].isalpha() and not v[2].isalpha():
        v = v[2:]
    elif len(v) == 2 and v.isalpha():
        v = ""
    return len(v) < 5 or len(set(v)) == 1
cli = P.search([("primavera_customer_code", "!=", False), ("primavera_supplier_code", "=", False), ("vat", "!=", False)])
forn = P.search([("primavera_supplier_code", "!=", False), ("primavera_customer_code", "=", False), ("vat", "!=", False)])
por_vat = {}
for p in forn:
    if not ficticio(p.vat):
        por_vat.setdefault(p.vat, []).append(p)
pares = []
for p in cli:
    if not ficticio(p.vat) and p.vat in por_vat:
        for f in por_vat[p.vat]:
            pares.append((p.vat, p.id, p.primavera_customer_code, p.name[:22], f.id, f.primavera_supplier_code, f.name[:22], str(p.create_date)[:10], str(f.create_date)[:10]))
print("R fichas separadas de cliente e de fornecedor com o mesmo NIF válido:", len(pares))
for x in pares[:15]:
    print("R   ", x)
print("R fichas cliente+fornecedor (uma só):", P.search_count([("primavera_customer_code", "!=", False), ("primavera_supplier_code", "!=", False)]))
