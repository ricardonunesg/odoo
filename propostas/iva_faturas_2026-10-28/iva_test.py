# IVA — ensaio em cópia isolada: reimportar as 895 FA/FAT 2026 com o código actual e comparar com o Primavera.
import copy, json
from collections import defaultdict
from unittest import mock
from odoo.addons.primavera_connector.models import primavera_connection as M
D = json.load(open("/out/iva_data.json"))
c = env["primavera.connection"].browse(1)
AM = env["account.move"].sudo()
def R(*a): print("R", *a, flush=True)
def edita(self, ep, strict=False):
    p = ep.split("/")
    if "/Vendas/Docs/Edita/" in ep:
        return copy.deepcopy(D["api"].get(f"{p[-3]}/{p[-2]}/{p[-1]}"))
    if "/Base/Artigos/Edita/" in ep:
        return copy.deepcopy(D["art"].get(p[-1]))
    return None
def compara(tag):
    moves = {m.primavera_ref: m for m in AM.search([("primavera_ref", "=like", "F%/2026/%")])}
    dif = []
    for k, h in D["H"].items():
        m = moves.get(k)
        if not m:
            dif.append((k, "falta")); continue
        # por taxa
        o = defaultdict(lambda: [0.0, 0.0])
        for l in m.invoice_line_ids.filtered(lambda x: x.display_type == "product"):
            rate = round(sum(l.tax_ids.mapped("amount")), 2)
            o[rate][0] += l.price_subtotal; o[rate][1] += l.price_total - l.price_subtotal
        p = defaultdict(lambda: [0.0, 0.0])
        for cod, taxa, inc, val in D["RI"].get(k, []):
            p[round(taxa if val or taxa == 0 else taxa, 2) if val else (0.0 if not val and not taxa else taxa)][0] += inc
            p[round(taxa if val else (0.0 if not val and not taxa else taxa), 2)][1] += val
        div = abs(h["iva"] - m.amount_tax)
        dtot = abs(h["total"] - m.amount_total)
        taxas_o = {r for r, v in o.items() if abs(v[0]) > 0.005}
        taxas_p = {round(t, 2) for _, t, inc, val in D["RI"].get(k, []) if abs(inc) > 0.005 and (val or t == 0)}
        if div > 0.05 or dtot > 0.05 or taxas_o != taxas_p:
            dif.append((k, f"IVA P {h['iva']:.2f} O {m.amount_tax:.2f} | total P {h['total']:.2f} O {m.amount_total:.2f} | taxas P {sorted(taxas_p)} O {sorted(taxas_o)} | anulada {h['anulado']}"))
    cent = sum(1 for k, h in D["H"].items() if k in moves and 0.005 < abs(h["total"] - moves[k].amount_total) <= 0.05)
    R(f"{tag}: faturas com diferença de IVA/total > 0,05 € ou taxa diferente: {len(dif)} | só cêntimos (≤0,05 €): {cent}")
    for d in dif: R("   ", *d)
    return dif

antes = compara("ANTES (como está em produção)")
for p in [mock.patch.object(M.PrimaveraConnection, "_edita", edita),
          mock.patch.object(M.PrimaveraConnection, "_sql_connection", lambda self: None)]:
    p.start()
mx = {t: max(int(k.split("/")[2]) for k in D["H"] if k.startswith(t + "/")) for t in ("FA", "FAT")}
for t in ("FA", "FAT"):
    st = c._import_faturas_doc(t, "2026", 0, mx[t] + 1, 5, None)
    R(f"reimportação {t}: {st}")
depois = compara("DEPOIS de reimportar com o código actual")
fa176 = AM.search([("primavera_ref", "=", "FA/2026/176")])
R("FA/2026/176 depois:", fa176.amount_untaxed, fa176.amount_tax, fa176.amount_total, [(l.product_id.default_code, l.tax_ids.mapped("name")) for l in fa176.invoice_line_ids if l.product_id][:4])
fa172 = AM.search([("primavera_ref", "=", "FA/2026/172")])
R("FA/2026/172 depois:", fa172.amount_untaxed, fa172.amount_tax, fa172.amount_total, [(l.name[:30], l.tax_ids.mapped("name")) for l in fa172.invoice_line_ids if l.display_type == "product"][:4])
env.cr.rollback()
R("FIM (transacção desfeita)")
