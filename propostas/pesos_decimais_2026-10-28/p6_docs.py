# Ponto 6 — só leitura: efeito do arredondamento das unidades (3 casas peso / 4 volume / 2 boletim) nos documentos.
from collections import defaultdict
c = env["primavera.connection"].browse(1)
conn = c._sql_connection(); cur = conn.cursor()
cur.execute("SELECT Artigo, Peso, Volume, PesoLiquido, IntrastatPeso FROM Artigo")
A = {r[0].strip(): r[1:] for r in cur.fetchall()}
cr = env.cr

def analisa(nome, sql, qty_expr_note):
    cr.execute(sql)
    rows = cr.fetchall()
    n = len(rows); lp = lv = 0; docs = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0, ""])  # pb guardado, pb exacto, vol guardado, vol exacto
    ex = []
    for doc_id, doc_name, code, qty, pb, vol in rows:
        a = A.get(code)
        if not a: continue
        w, v = float(a[0] or 0), float(a[1] or 0)
        pb, vol, qty = float(pb or 0), float(vol or 0), float(qty or 0)
        # só compara quando o valor guardado veio do artigo (arredondado) — não quando foi escrito à mão
        if pb and abs(pb - w) < 0.001 and pb != w: lp += 1; ex.append((doc_name, code, w, pb))
        if vol and abs(vol - v) < 0.0001 and vol != v: lv += 1
        d = docs[doc_id]; d[4] = doc_name
        d[0] += qty * pb; d[2] += qty * vol
        d[1] += qty * (w if pb and abs(pb - w) < 0.001 else pb)
        d[3] += qty * (v if vol and abs(vol - v) < 0.0001 else vol)
    dp = sorted(((abs(d[1] - d[0]), d[4], round(d[0], 3), round(d[1], 3)) for d in docs.values()), reverse=True)
    dv = sorted(((abs(d[3] - d[2]), d[4], round(d[2], 4), round(d[3], 6)) for d in docs.values()), reverse=True)
    print(f"R {nome}: linhas {n} | peso unit. arredondado {lp} | volume unit. arredondado {lv} | documentos {len(docs)}"
          f" | docs com diferença peso ≥0,001 kg: {sum(1 for x in dp if x[0] >= 0.001)} | volume ≥0,0001 m³: {sum(1 for x in dv if x[0] >= 0.0001)}")
    print(f"R    maiores diferenças peso (dif, doc, Odoo, exacto): {[(round(x[0],3),)+x[1:] for x in dp[:5]]}")
    print(f"R    maiores diferenças volume: {[(round(x[0],6),)+x[1:] for x in dv[:5]]}")
    print(f"R    exemplos linha (doc, artigo, Primavera, Odoo): {ex[:4]}")

analisa("Boletins de análises (linhas, 2 casas)", """select b.id, b.name, l.product_code, l.quantidade, l.peso_bruto, 0
  from boletim_analises_linha l join boletim_analises b on b.id=l.documento_id""", "")

# Artigos com mais casas que os campos dos documentos
w3 = [(k, a[0]) for k, a in A.items() if a[0] and round(a[0], 3) != a[0]]
v4 = [(k, a[1]) for k, a in A.items() if a[1] and round(a[1], 4) != a[1]]
w2 = [(k, a[0]) for k, a in A.items() if a[0] and round(a[0], 2) != a[0]]
print("R artigos com peso >3 casas:", len(w3), w3[:8])
print("R artigos com volume >4 casas:", len(v4), "| peso >2 casas (boletins):", len(w2))
# Peso líquido do Primavera: artigo vs linha (IntrastatMassaLiq) — que valor é?
pl_art = sum(1 for a in A.values() if a[2])
print("R artigos com PesoLiquido no Primavera:", pl_art, "| exemplos (artigo, Peso, PesoLiquido, IntrastatPeso):",
      [(k, a[0], a[2], a[3]) for k, a in A.items() if a[2]][:6])
cur.execute("""SELECT TOP 12 cd.TipoDoc, cd.NumDoc, ld.Artigo, ld.Quantidade, ld.Unidade, ld.IntrastatMassaLiq
  FROM LinhasDoc ld JOIN CabecDoc cd ON cd.Id=ld.IdCabecDoc WHERE cd.TipoDoc='ECL' AND ld.Artigo LIKE 'OL.%' AND cd.Data >= '2026-09-01' ORDER BY cd.Data DESC""")
print("R ECL Primavera (tipo, nº, artigo, qtd, unid, IntrastatMassaLiq):", [tuple(str(x) for x in r) for r in cur.fetchall()])
cr.execute("""select so.name, pp.default_code, sol.product_uom_qty, sol.peso_liquido, sol.peso_bruto, sol.caixas
  from sale_order_line sol join sale_order so on so.id=sol.order_id join product_product pp on pp.id=sol.product_id
  where pp.default_code like 'OL.%%' order by sol.id desc limit 6""")
print("R ECL Odoo (nº, artigo, qtd, P.líq unit, P.bruto unit, caixas):", cr.fetchall())
cr.execute("select count(*) from sale_order_line where display_type is null and product_id is not null and coalesce(caixas,0)=0")
print("R linhas ECL com caixas=0 (unidade ≠ CX):", cr.fetchall())
cr.execute("select count(*), count(*) filter (where caixas=0 and coalesce(peso_bruto,0)<>0 and product_code not like 'PAL%%') from packing_list_line")
print("R linhas PL / com caixas 0 e peso (não-palete):", cr.fetchall())
conn.close()
