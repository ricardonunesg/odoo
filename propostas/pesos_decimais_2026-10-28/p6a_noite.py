c = env["primavera.connection"].browse(1); cur = c._sql_connection().cursor()
cur.execute("SELECT Artigo, Peso, Volume FROM Artigo"); A = {r[0].strip(): (r[1] or 0.0, r[2] or 0.0) for r in cur.fetchall()}
ecls = env["sale.order"].sudo().search(c._ecl_resync_domain())
ls = ecls.order_line.filtered(lambda l: not l.display_type and l.product_id.default_code in A)
anul = ls.filtered(lambda l: l.order_id.state == "cancel")
ok = ls - anul
print("R ECLs em curso:", len(ecls), "| linhas activas:", len(ok), "| peso igual ao Primavera:", sum(1 for l in ok if l.peso_bruto == A[l.product_id.default_code][0]),
      "| volume igual:", sum(1 for l in ok if l.volume == A[l.product_id.default_code][1]), "| linhas em ECLs anuladas (não mexidas):", len(anul))
print("R diferentes (activas):", [(l.order_id.name, l.product_id.default_code, l.peso_bruto, A[l.product_id.default_code][0], l.volume, A[l.product_id.default_code][1]) for l in ok if l.peso_bruto != A[l.product_id.default_code][0] or l.volume != A[l.product_id.default_code][1]][:10])
env.cr.rollback()
