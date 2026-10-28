import json
D = json.load(open("/dev/stdin")) if False else None
c = env["primavera.connection"].browse(1); cur = c._sql_connection().cursor()
for n in ("ECL/2026/142", "ECL/2026/159", "ECL/2026/172"):
    so = env["sale.order"].sudo().search([("name", "=", n)], limit=1)
    print("R", n, "| estado", so.state, "| etapa", so.stage_id.name, "| faturas", [(m.name, m.state) for m in so.invoice_ids])
cur.execute("""SELECT a.Artigo, a.Peso, a.PesoLiquido, a.Descricao FROM Artigo a WHERE a.Artigo IN ('EMB.01.021.10000.40','EMB.01.002.01000.01','CAPS.48.01.05.10')""")
print("R artigos FAT/2026/47 sem peso bruto:", [tuple(str(x) for x in r) for r in cur.fetchall()])
cur.execute("SELECT COUNT(*) FROM Artigo WHERE ISNULL(Peso,0)=0 AND PesoLiquido>0 AND ArtigoAnulado=0")
print("R artigos activos com peso líquido mas SEM peso bruto no Primavera:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM Artigo WHERE PesoLiquido > Peso AND Peso>0 AND ArtigoAnulado=0")
print("R artigos com líquido > bruto:", cur.fetchone()[0])
env.cr.execute("""select so.name, pp.default_code, sol.peso_liquido, sol.peso_bruto from sale_order_line sol join sale_order so on so.id=sol.order_id join product_product pp on pp.id=sol.product_id
 where sol.peso_liquido<>0 and sol.peso_liquido=sol.peso_bruto and pp.default_code not like 'PAL%%' and so.id in (select id from sale_order where state not in ('cancel'))""")
rows = env.cr.fetchall()
cur.execute("SELECT Artigo, Peso, PesoLiquido FROM Artigo"); A = {r[0].strip(): (r[1], r[2]) for r in cur.fetchall()}
print("R ECL com líquido = bruto (ECL, artigo, líquido linha, artigo Peso/PesoLiquido):", [(r[0], r[1], float(r[2]), A.get(r[1])) for r in rows if A.get(r[1]) and A[r[1]][1] and A[r[1]][1] != A[r[1]][0]][:12])
env.cr.rollback()
