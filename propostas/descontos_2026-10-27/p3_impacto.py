import json
from collections import Counter, defaultdict
from odoo.tools import float_round
c = env['primavera.connection'].browse(1)
dp = env['decimal.precision'].precision_get('Discount')
cur = c._sql_connection().cursor()
cur.execute("""SELECT c.TipoDoc + '/' + c.Serie + '/' + CAST(c.NumDoc AS varchar), c.TipoDoc, l.NumLinha, l.Artigo,
                      ISNULL(l.Desconto1,0), ISNULL(l.Desconto2,0), ISNULL(l.Desconto3,0), ISNULL(c.DescEntidade,0), ISNULL(l.NaoSujDescontoCabec,0),
                      c.TotalMerc, ISNULL(c.TotalDesc,0), ISNULL(c.TotalIva,0), ISNULL(c.TotalOutros,0)
               FROM CabecDoc c JOIN LinhasDoc l ON l.IdCabecDoc=c.Id
               WHERE c.TipoDoc IN ('FA','FAT','ECL') AND c.Serie='2026' AND l.Artigo IS NOT NULL AND LTRIM(l.Artigo)<>''
                 AND c.Id IN (SELECT c2.Id FROM CabecDoc c2 JOIN LinhasDoc l2 ON l2.IdCabecDoc=c2.Id
                              WHERE c2.TipoDoc IN ('FA','FAT','ECL') AND c2.Serie='2026'
                                AND (ISNULL(l2.Desconto1,0)<>0 OR ISNULL(l2.Desconto2,0)<>0 OR ISNULL(l2.Desconto3,0)<>0 OR ISNULL(c2.DescEntidade,0)<>0))
               ORDER BY 1, l.NumLinha""")
docs = defaultdict(lambda: {"linhas": []})
for ref, tipo, n, art, d1, d2, d3, de, naosuj, merc, tdesc, tiva, tout in cur.fetchall():
    f = (1 - float(d1) / 100) * (1 - float(d2) / 100) * (1 - float(d3) / 100) * (1 if naosuj else (1 - float(de) / 100))
    eff = float_round((1 - f) * 100, precision_digits=dp)
    d = docs[ref]; d["tipo"] = tipo; d["prim"] = {"liq": round(float(merc) - float(tdesc) + float(tout), 2), "iva": float(tiva), "desc": float(tdesc)}
    d["linhas"].append((art.strip(), eff))
AM = env['account.move'].sudo(); SO = env['sale.order'].sudo().with_context(active_test=False)
corr = []; st = Counter(); impacto = defaultdict(lambda: [0, 0.0, 0.0]); desal = []; especiais = []
for ref, d in docs.items():
    if d["tipo"] == "ECL":
        rec = SO.search([('primavera_ecl_ref', '=', ref)], limit=1)
        if not rec:
            st["ECL não existe no Odoo (anulada não importada)"] += 1; continue
        ol = rec.order_line.filtered(lambda l: not l.display_type and l.product_id).sorted(lambda l: (l.sequence, l.id))
        estado = f"ECL {rec.state} / {rec.stage_id.name}"
        untaxed, tax = rec.amount_untaxed, rec.amount_tax
    else:
        rec = AM.search([('primavera_ref', '=', ref)], limit=1)
        ol = rec.invoice_line_ids.filtered(lambda l: l.display_type == 'product' and l.product_id).sorted(lambda l: (l.sequence, l.id))
        estado = f"fatura {rec.state}"
        untaxed, tax = rec.amount_untaxed, rec.amount_tax
    st[estado] += 1
    if [a for a, _ in d["linhas"]] != [l.product_id.default_code for l in ol]:
        desal.append((ref, len(d["linhas"]), len(ol))); continue
    n = 0
    for (art, eff), l in zip(d["linhas"], ol):
        if abs((l.discount or 0) - eff) > 1e-9:
            corr.append({"modelo": l._name, "line": l.id, "ref": ref, "art": art, "de": l.discount or 0.0, "para": eff, "estado": estado})
            n += 1
    if n:
        k = d["tipo"] if d["tipo"] == "ECL" else "FA/FAT"
        impacto[k][0] += 1; impacto[k][1] += round(untaxed - d["prim"]["liq"], 2); impacto[k][2] += round(tax - d["prim"]["iva"], 2)
    if "posted" in estado or "cancel" in estado:
        especiais.append((ref, estado, n))
print("R documentos com desconto no Primavera:", len(docs), "| estado no Odoo:", dict(st))
print("R linhas a corrigir:", len(corr), Counter((x["modelo"], x["para"]) for x in corr))
print("R impacto actual (nº docs, Odoo − Primavera sem IVA, IVA):", {k: (v[0], round(v[1], 2), round(v[2], 2)) for k, v in impacto.items()})
print("R não encaixam 1-a-1:", desal)
print("R casos especiais (lançada/cancelada):", especiais)
json.dump(corr, open('/tmp/p3_corr.json', 'w'))
