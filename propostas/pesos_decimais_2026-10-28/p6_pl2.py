c = env["primavera.connection"].browse(1); cur = c._sql_connection().cursor()
cur.execute("SELECT Artigo, Peso, PesoLiquido FROM Artigo WHERE PesoLiquido > 0")
PL = {r[0].strip(): (r[1] or 0, r[2]) for r in cur.fetchall()}
for nome, sql in [("Faturas", "select am.name, pp.default_code from account_move_line aml join account_move am on am.id=aml.move_id join product_product pp on pp.id=aml.product_id where aml.display_type='product' and am.move_type='out_invoice' and coalesce(aml.peso_liquido,0)=0"),
                  ("ECL", "select so.name, pp.default_code from sale_order_line sol join sale_order so on so.id=sol.order_id join product_product pp on pp.id=sol.product_id where sol.display_type is null and coalesce(sol.peso_liquido,0)=0")]:
    env.cr.execute(sql); rows = [r for r in env.cr.fetchall() if r[1] in PL and not r[1].startswith("PAL")]
    print("R", nome, "linhas sem peso líquido cujo artigo TEM peso líquido no Primavera:", len(rows), "| documentos:", len({r[0] for r in rows}), "| artigos:", sorted({r[1] for r in rows})[:12])
env.cr.execute("select pl.name, l.product_code, l.peso_liquido, l.caixas, l.pliquidot from packing_list_line l join packing_list pl on pl.id=l.packing_list_id where l.product_code like 'OLIV%%'")
print("R PL com OLIV:", env.cr.fetchall(), "| Primavera líquido:", PL.get("OLIV.001.01.00350.01"))
