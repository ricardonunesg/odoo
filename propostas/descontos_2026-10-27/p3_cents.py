# Só leitura: confirma que as diferenças de cêntimos resultam só do método de arredondamento.
from collections import defaultdict, Counter
from odoo.tools import float_round as fr
c = env["primavera.connection"].browse(1)
cur = c._sql_connection().cursor()
cur.execute("""SELECT c.TipoDoc + '/' + c.Serie + '/' + CAST(c.NumDoc AS varchar), c.TotalMerc - ISNULL(c.TotalDesc,0) + ISNULL(c.TotalOutros,0), c.TotalIva,
                      l.Artigo, l.Quantidade, l.PrecUnit, ISNULL(l.Desconto1,0), ISNULL(c.DescEntidade,0), l.PrecoLiquido, l.TaxaIva, l.TotalIva, l.TotalIliquido
               FROM CabecDoc c JOIN LinhasDoc l ON l.IdCabecDoc=c.Id
               WHERE c.TipoDoc IN ('FA','FAT','ECL') AND c.Serie='2026' AND (ISNULL(l.PrecoLiquido,0)<>0 OR ISNULL(l.TotalIva,0)<>0 OR (l.Artigo IS NOT NULL AND l.Artigo<>''))
                 AND c.Id IN (SELECT IdCabecDoc FROM LinhasDoc l2 JOIN CabecDoc c2 ON c2.Id=l2.IdCabecDoc WHERE ISNULL(l2.Desconto1,0)<>0 OR ISNULL(c2.DescEntidade,0)<>0)
               ORDER BY 1""")
P = defaultdict(lambda: {"l": []})
for ref, liq, iva, art, q, pu, d1, de, pl, tx, liva, tili in cur.fetchall():
    P[ref]["liq"], P[ref]["iva"] = float(liq), float(iva)
    P[ref]["l"].append(((art or "").strip(), float(q or 0), float(pu or 0), c._desconto_linha({"Desconto1": d1}, {"DescEntidade": de}),
                        float(pl or 0), float(tx or 0), float(liva or 0), float(tili or 0)))
res = Counter(); ex = []
for ref, p in P.items():
    if ref.startswith("ECL"):
        d = env["sale.order"].search([("primavera_ecl_ref", "=", ref)], limit=1)
        ol = d.order_line.filtered(lambda l: not l.display_type and l.product_id)
        o_lines = [(l.product_id.default_code, l.product_uom_qty, l.price_unit, l.discount, sum(l.tax_id.mapped("amount"))) for l in ol]
    else:
        d = env["account.move"].search([("primavera_ref", "=", ref)], limit=1)
        ol = d.invoice_line_ids.filtered(lambda l: l.display_type == "product" and l.product_id)
        o_lines = [(l.product_id.default_code, l.quantity, l.price_unit, l.discount, sum(l.tax_ids.mapped("amount"))) for l in ol]
    du, di = round(d.amount_untaxed - p["liq"], 2), round(d.amount_tax - p["iva"], 2)
    if abs(du) < 0.005 and abs(di) < 0.005:
        res["igual"] += 1; continue
    pl_art = [x for x in p["l"] if x[0]]
    mesmos_dados = sorted((a, round(q, 4), round(pu, 6), dd) for a, q, pu, dd, *_ in pl_art) == sorted((a, round(q, 4), round(pu, 6), dd) for a, q, pu, dd, _t in o_lines)
    mesmas_taxas = sorted((a, tx) for a, q, pu, dd, pl, tx, *_ in pl_art) == sorted((a, t) for a, q, pu, dd, t in o_lines)
    # Primavera: por linha round(bruto) − round(desconto); IVA por linha. Odoo: round(q×p×(1−d)); IVA global sobre base não arredondada.
    prim_metodo = round(sum(fr(q * pu, 2) - fr(q * pu * dd / 100, 2) for a, q, pu, dd, *_ in pl_art) + sum(x[4] for x in p["l"] if not x[0]), 2)
    odoo_metodo = round(sum(fr(q * pu * (1 - dd / 100), 2) for a, q, pu, dd, t in o_lines), 2)
    base = defaultdict(float)
    for a, q, pu, dd, t in o_lines:
        base[t] += q * pu * (1 - dd / 100)
    odoo_iva_metodo = round(sum(fr(b * t / 100, 2) for t, b in base.items()), 2)
    explicado = mesmos_dados and mesmas_taxas and abs(du) <= 0.02 and abs(di) <= 0.02
    k = "cêntimos — só arredondamento" if explicado else "NÃO explicado só por arredondamento"
    res[k] += 1
    if not explicado:
        ex.append((ref, du, di, "mesmos dados" if mesmos_dados else "DADOS DIFERENTES", "mesmas taxas" if mesmas_taxas else "TAXA DE IVA DIFERENTE"))
print("R 113 documentos:", dict(res))
print("R não explicados (ref, dif. sem IVA, dif. IVA, mesmos dados?, …):", ex)
