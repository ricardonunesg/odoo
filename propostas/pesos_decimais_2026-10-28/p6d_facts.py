# Só leitura: PL/2026/0001 (id 36) por artigo + 132 artigos com líquido e sem bruto.
from collections import Counter
c = env["primavera.connection"].browse(1); cur = c._sql_connection().cursor()
cur.execute("SELECT Artigo, Peso, PesoLiquido, Volume, Descricao, ArtigoAnulado, UnidadeVenda FROM Artigo")
A = {r[0].strip(): r[1:] for r in cur.fetchall()}
pl = env["packing.list"].sudo().browse(36)
print("R PL", pl.name, pl.state, "| fatura", pl.fatura_id.name, "| guardado: líquido", pl.total_peso_liquido, "bruto", pl.total_peso_bruto, "volume", pl.total_volume, "caixas", pl.total_caixas)
cur.execute("""SELECT ld.Artigo, ld.Quantidade, ld.Unidade, ld.IntrastatMassaLiq FROM LinhasDoc ld JOIN CabecDoc cd ON cd.Id=ld.IdCabecDoc
 WHERE cd.TipoDoc='FA' AND cd.Serie='2026' AND cd.NumDoc=171 AND ld.Artigo IS NOT NULL ORDER BY ld.NumLinha""")
prim = [(r[0].strip(), float(r[1]), r[2], float(r[3] or 0)) for r in cur.fetchall()]
tot = {"actual": 0.0, "proposto": 0.0, "bruto": 0.0, "prim_linha": 0.0}
for l in pl.line_ids.sorted("sequence"):
    a = A.get(l.product_code) or (0, 0, 0, "", 0, "")
    pf = next((p for p in prim if p[0] == l.product_code), None)
    liq_linha_prim = pf[3] if pf else 0.0
    proposto = 0.0 if l.is_palete else l.caixas * (liq_linha_prim or float(a[1] or 0))
    tot["actual"] += l.pliquidot; tot["proposto"] += proposto; tot["bruto"] += l.pbrutot
    print(f"R | {l.product_code} | {l.caixas} cx | bruto/cx Odoo {l.peso_bruto} Prim {a[0]} | líq/cx guardado {l.peso_liquido} | linha Prim {liq_linha_prim} | artigo Prim {a[1]} | líq linha actual {l.pliquidot} | proposto {round(proposto,3)} | dif {round(proposto - l.pliquidot,3)}{' | PALETE' if l.is_palete else ''}")
print("R somas linhas: líquido actual", round(tot["actual"], 3), "| proposto", round(tot["proposto"], 3), "| bruto", round(tot["bruto"], 3))
print("R Primavera FA/2026/171 (linhas):", prim)
# 132 artigos: líquido sem bruto
sem = {k: v for k, v in A.items() if not (v[0] or 0) and (v[1] or 0) > 0 and not v[4]}
pref = Counter(k.split(".")[0] for k in sem)
print("R artigos activos com líquido e sem bruto:", len(sem), "| por família:", pref.most_common())
print("R exemplos:", [(k, v[1], v[3], v[2], v[5]) for k, v in list(sem.items())[:12]])
codes = tuple(sem) or ("-",)
for nome, sql in [("linhas ECL", "select count(*), count(distinct order_id) from sale_order_line sol join product_product pp on pp.id=sol.product_id where pp.default_code in %s"),
                  ("linhas fatura", "select count(*), count(distinct move_id) from account_move_line aml join product_product pp on pp.id=aml.product_id where aml.display_type='product' and pp.default_code in %s"),
                  ("linhas PL", "select count(*), count(distinct packing_list_id) from packing_list_line where product_code in %s")]:
    env.cr.execute(sql, (codes,)); print("R uso em", nome, "(linhas, documentos):", env.cr.fetchone())
env.cr.execute("select pt.default_code, pt.weight from product_template pt where pt.default_code in %s and coalesce(pt.weight,0)<>0", (codes,))
print("R no Odoo com peso bruto ≠ 0 (deveria ser 0):", env.cr.fetchall())
env.cr.execute("""select so.name, pp.default_code, sol.product_uom_qty, sol.peso_liquido, sol.peso_bruto from sale_order_line sol join sale_order so on so.id=sol.order_id join product_product pp on pp.id=sol.product_id
 where pp.default_code in %s order by so.id desc limit 6""", (codes,))
print("R exemplos em ECLs (ECL, artigo, qtd, líq, bruto):", env.cr.fetchall())
gl = {k: v for k, v in A.items() if (v[0] or 0) > 0 and not (v[1] or 0) and not v[4]}
print("R artigos activos com bruto e SEM líquido:", len(gl), Counter(k.split(".")[0] for k in gl).most_common(), list(gl)[:10])
nada = [k for k, v in A.items() if not (v[0] or 0) and not (v[1] or 0) and not v[4]]
print("R artigos activos sem bruto nem líquido:", len(nada), Counter(k.split(".")[0] for k in nada).most_common(8))
env.cr.rollback()
