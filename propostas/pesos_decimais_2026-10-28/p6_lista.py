# Só leitura: documentos com diferença relevante (peso ≥ 1 kg ou volume ≥ 0,01 m³) entre o guardado e o exacto do Primavera.
from collections import defaultdict
c = env["primavera.connection"].browse(1); cur = c._sql_connection().cursor()
cur.execute("SELECT Artigo, Peso, Volume, PesoLiquido FROM Artigo")
A = {r[0].strip(): (float(r[1] or 0), float(r[2] or 0), float(r[3] or 0)) for r in cur.fetchall()}
cr = env.cr
LP, LV = 1.0, 0.01
def rel(sql):
    cr.execute(sql)
    docs = defaultdict(lambda: {"pb": 0.0, "pbx": 0.0, "v": 0.0, "vx": 0.0, "info": None})
    for doc_id, info, code, qty, pb, vol in cr.fetchall():
        a = A.get(code)
        if not a: continue
        qty, pb, vol = float(qty or 0), float(pb or 0), float(vol or 0)
        d = docs[doc_id]; d["info"] = info
        d["pb"] += qty * pb; d["v"] += qty * vol
        d["pbx"] += qty * (a[0] if pb and abs(pb - a[0]) < 0.001 else pb)
        d["vx"] += qty * (a[1] if vol and abs(vol - a[1]) < 0.0001 else vol)
    out = [(d["info"], round(d["pbx"] - d["pb"], 3), round(d["vx"] - d["v"], 4), round(d["pb"], 3), round(d["v"], 4)) for d in docs.values()
           if abs(d["pbx"] - d["pb"]) >= LP or abs(d["vx"] - d["v"]) >= LV]
    return sorted(out, key=lambda x: -abs(x[1]) - 100 * abs(x[2]))
fat = rel("""select am.id, am.name||' | '||am.state||' | '||am.invoice_date||' | '||coalesce(rp.name,'')||' | enviada:'||coalesce(am.is_move_sent::text,'?'), pp.default_code,
  coalesce(nullif(aml.caixas,0), aml.quantity), aml.peso_bruto, aml.volume
  from account_move_line aml join account_move am on am.id=aml.move_id join product_product pp on pp.id=aml.product_id left join res_partner rp on rp.id=am.partner_id
  where aml.display_type='product' and am.move_type in ('out_invoice','out_refund')""")
print("R FATURAS com diferença relevante:", len(fat))
for x in fat: print("R   ", x)
pl = rel("""select pl.id, pl.name||' | '||pl.state||' | '||coalesce(am.name,'sem fatura'), l.product_code, l.caixas, l.peso_bruto, l.volume
  from packing_list_line l join packing_list pl on pl.id=l.packing_list_id left join account_move am on am.id=pl.fatura_id""")
print("R PACKING LISTS com diferença relevante:", len(pl))
for x in pl: print("R   ", x)
# ECLs em curso que a re-sync não corrige (bloqueadas) e porquê
SO = env["sale.order"].sudo()
ecls = SO.search(c._ecl_resync_domain())
bloq = []
for so in ecls:
    posted = any(m.state == "posted" for m in so.invoice_ids)
    if so.state in ("cancel", "done") or posted:
        n = sum(1 for l in so.order_line if not l.display_type and l.product_id.default_code in A
                and ((l.peso_bruto and l.peso_bruto != A[l.product_id.default_code][0]) or (l.volume and l.volume != A[l.product_id.default_code][1])))
        if n:
            mot = "fatura emitida " + ",".join(so.invoice_ids.filtered(lambda m: m.state == "posted").mapped("name")) if posted else f"estado {so.state}"
            bloq.append((so.name, so.stage_id.name, mot, n))
print("R ECLs em curso que NÃO ficam corrigidas:", len(bloq), "| linhas:", sum(b[3] for b in bloq))
for b in bloq: print("R   ", b)
print("R ECLs em curso que ficam corrigidas na próxima re-sync:", len(ecls) - len(bloq))
# Peso líquido = bruto (problema C) em documentos
for nome, sql in [("PL", """select pl.name||' | '||pl.state, l.product_code, l.caixas, l.peso_liquido from packing_list_line l join packing_list pl on pl.id=l.packing_list_id where l.product_code not like 'PAL%%'"""),
                  ("Fatura", """select am.name||' | '||am.state, pp.default_code, coalesce(nullif(aml.caixas,0), aml.quantity), aml.peso_liquido from account_move_line aml join account_move am on am.id=aml.move_id join product_product pp on pp.id=aml.product_id where aml.display_type='product' and am.move_type='out_invoice' and pp.default_code not like 'PAL%%'""")]:
    cr.execute(sql); res = defaultdict(float)
    for info, code, qty, pl_ in cr.fetchall():
        a = A.get(code)
        if not a or not a[2]: continue
        pl_ = float(pl_ or 0)
        efect = pl_ if (nome == "Fatura") else pl_
        if nome == "PL" and abs(pl_ - a[0]) < 0.0005 and abs(a[0] - a[2]) > 0.0005:
            res[info] += float(qty or 0) * (pl_ - a[2])
        if nome == "Fatura" and not pl_:
            res[info] += 0.0
    if nome == "PL":
        print("R PL com peso líquido = bruto (kg a mais):", [(k, round(v, 3)) for k, v in res.items()])
    else:
        print("R faturas com linhas sem peso líquido (artigo com PesoLiquido): ", len(res), sorted(res)[:60])
