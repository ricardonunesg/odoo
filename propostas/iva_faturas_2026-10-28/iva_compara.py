# Só leitura: IVA das faturas FA/FAT 2026 — Primavera (SQL) vs Odoo.
import json
from collections import defaultdict
c = env["primavera.connection"].browse(1); cur = c._sql_connection().cursor()
cur.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='ResumoIva'")
print("R ResumoIva colunas:", [r[0] for r in cur.fetchall()])
cur.execute("""SELECT cd.Id, cd.TipoDoc, cd.Serie, cd.NumDoc, cd.Entidade, cd.TotalMerc, cd.TotalDesc, cd.TotalIva, cd.TotalDocumento, cd.TotalOutros,
  cd.EspacoFiscal, cd.RegimeIva, cd.ArredondamentoIva, cd.Data, ISNULL(cs.Anulado,0)
  FROM CabecDoc cd LEFT JOIN CabecDocStatus cs ON cs.IdCabecDoc=cd.Id WHERE cd.TipoDoc IN ('FA','FAT') AND cd.Serie='2026'""")
H = {}
for r in cur.fetchall():
    H[f"{r[1]}/{r[2]}/{r[3]}"] = dict(id=r[0], ent=r[4], merc=float(r[5] or 0), desc=float(r[6] or 0), iva=float(r[7] or 0), total=float(r[8] or 0),
                                     outros=float(r[9] or 0), espaco=r[10], regime=r[11], arred=r[12], data=str(r[13])[:10], anulado=bool(r[14]))
cur.execute("""SELECT cd.TipoDoc, cd.Serie, cd.NumDoc, ld.NumLinha, ld.Artigo, ld.Quantidade, ld.CodIva, ld.TaxaIva, ld.TotalIliquido, ld.TotalDA, ld.TotalDC, ld.TotalDF,
  ld.TotalIva, ld.PrecoLiquido, ld.TipoLinha, ld.PercIncidenciaIVA, ld.Desconto1, ld.Desconto2, ld.DescontoComercial
  FROM LinhasDoc ld JOIN CabecDoc cd ON cd.Id=ld.IdCabecDoc WHERE cd.TipoDoc IN ('FA','FAT') AND cd.Serie='2026' ORDER BY cd.Id, ld.NumLinha""")
L = defaultdict(list)
for r in cur.fetchall():
    L[f"{r[0]}/{r[1]}/{r[2]}"].append(dict(n=r[3], art=(r[4] or "").strip(), qty=float(r[5] or 0), cod=r[6], taxa=float(r[7] or 0), iliq=float(r[8] or 0),
        da=float(r[9] or 0), dc=float(r[10] or 0), df=float(r[11] or 0), iva=float(r[12] or 0), liq=float(r[13] or 0), tipo=r[14], inc=r[15]))
AM = env["account.move"].sudo()
moves = {m.primavera_ref: m for m in AM.search([("primavera_ref", "!=", False), ("move_type", "in", ("out_invoice", "out_refund"))])}
print("R Primavera FA/FAT 2026:", len(H), "| anuladas:", sum(1 for h in H.values() if h["anulado"]), "| no Odoo:", sum(1 for k in H if k in moves))
rows = []
for k, h in sorted(H.items(), key=lambda x: (x[0].split("/")[0], int(x[0].split("/")[2]))):
    m = moves.get(k)
    if not m:
        rows.append(dict(doc=k, falta=True, anulado=h["anulado"])); continue
    # Primavera por taxa (linhas)
    pt = defaultdict(lambda: [0.0, 0.0])
    for l in L[k]:
        if l["art"] or l["iliq"]:
            pt[(l["cod"], l["taxa"])][0] += l["liq"]; pt[(l["cod"], l["taxa"])][1] += l["iva"]
    ot = defaultdict(lambda: [0.0, 0.0])
    olines = m.invoice_line_ids.filtered(lambda x: x.display_type == "product")
    for ol in olines:
        rate = sum(ol.tax_ids.mapped("amount"))
        ot[rate][0] += ol.price_subtotal; ot[rate][1] += ol.price_total - ol.price_subtotal
    # linhas: emparelhar por artigo + quantidade (linhas sem artigo: por valor)
    pl = [l for l in L[k] if l["art"] or l["iliq"]]
    livres = list(olines)
    dif_taxa = []
    for l in pl:
        cand = [o for o in livres if (o.product_id.default_code or "") == l["art"] and abs(o.quantity - l["qty"]) < 0.0005] if l["art"] else \
               [o for o in livres if not o.product_id and abs(o.price_subtotal - l["liq"]) < 0.01]
        ol = cand[0] if cand else None
        if ol: livres.remove(ol)
        orate = sum(ol.tax_ids.mapped("amount")) if ol else None
        if ol is None or abs((orate or 0) - l["taxa"]) > 0.001:
            dif_taxa.append((l["n"], l["art"], l["cod"], l["taxa"], ol.product_id.default_code if ol else None, orate, [t.name for t in ol.tax_ids] if ol else None, l["qty"], round(l["liq"], 2)))
    sobra = [(o.product_id.default_code, o.quantity, o.price_subtotal, [t.name for t in o.tax_ids]) for o in livres]
    rows.append(dict(doc=k, data=h["data"], ent=h["ent"], espaco=h["espaco"], regime=h["regime"], anulado=h["anulado"], state=m.state,
        p_base=round(h["merc"] - h["desc"], 2), o_base=round(m.amount_untaxed, 2), p_iva=round(h["iva"], 2), o_iva=round(m.amount_tax, 2),
        p_tot=round(h["total"], 2), o_tot=round(m.amount_total, 2), outros=h["outros"],
        p_taxas={f"{a}:{b}": [round(v[0], 2), round(v[1], 2)] for (a, b), v in pt.items()}, o_taxas={str(a): [round(v[0], 2), round(v[1], 2)] for a, v in ot.items()},
        n_p=len(pl), n_o=len(olines), dif_taxa=dif_taxa, sobra=sobra))
json.dump(rows, open("/tmp/iva_rows.json", "w"), default=str)
dif = [r for r in rows if not r.get("falta") and (abs(r["p_iva"] - r["o_iva"]) > 0.005 or abs(r["p_tot"] - r["o_tot"]) > 0.005 or abs(r["p_base"] - r["o_base"]) > 0.005 or r["dif_taxa"])]
print("R faturas comparadas:", sum(1 for r in rows if not r.get("falta")), "| com alguma diferença:", len(dif), "| em falta no Odoo:", [r["doc"] for r in rows if r.get("falta")][:20])
print("R com taxa de IVA diferente em alguma linha:", sum(1 for r in dif if r["dif_taxa"]), "| IVA diferente > 0,05 €:", sum(1 for r in dif if abs(r["p_iva"] - r["o_iva"]) > 0.05))
