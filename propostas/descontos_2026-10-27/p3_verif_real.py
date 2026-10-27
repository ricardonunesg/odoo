# Só leitura: nova consulta da verificação diária (SQL Primavera real) vs Odoo hoje e vs Odoo com a correcção simulada.
import json
corr = {x["line"]: x["para"] for x in json.load(open("/tmp/p3_corr.json")) if x["modelo"] == "sale.order.line"}
c = env["primavera.connection"].browse(1)
prim, series = c._verify_ecls_primavera()
SO = env["sale.order"].sudo().with_context(active_test=False)
hoje = depois = 0; ex_hoje = []; ex_depois = []
for ref, p in prim.items():
    so = SO.search([("primavera_ecl_ref", "=", ref)], limit=1)
    if not so or p["anulada"]:
        continue
    d_hoje = [x for x in c._verify_ecl_diffs(so, p) if "desconto" in x]
    # Odoo com a correcção: descontos das linhas segundo a lista
    ol = {}
    for l in so.order_line:
        if l.product_id and not l.display_type:
            ol.setdefault(l.product_id.default_code, set()).add(round(corr.get(l.id, l.discount or 0.0), 2))
    d_depois = [k for k in p["linhas"] if k in ol and p["linhas"][k][2] != ol[k]]
    if d_hoje:
        hoje += 1; ex_hoje.append((ref, d_hoje[0]))
    if d_depois:
        depois += 1; ex_depois.append((ref, d_depois))
print("R ECLs comparadas:", len(prim), "| com desconto diferente HOJE:", hoje, ex_hoje[:3])
print("R com desconto diferente DEPOIS da correcção (falsos alarmes):", depois, ex_depois[:5])
env.cr.rollback()
