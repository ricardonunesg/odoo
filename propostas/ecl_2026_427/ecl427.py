c = env["primavera.connection"].browse(1); cur = c._sql_connection().cursor()
so = env["sale.order"].sudo().search([("primavera_ecl_ref", "=", "ECL/2026/427")])
print("R Odoo:", so.id, so.name, so.state, so.stage_id.name, "| cliente:", so.partner_id.id, so.partner_id.name, so.partner_id.primavera_customer_code, "| criada", so.create_date, "| alterada", so.write_date)
print("R faturas:", so.primavera_fatura_refs, so.invoice_ids.mapped("name"), "| docs exportação:", len(so.ecl_doc_line_ids))
for m in env["mail.message"].sudo().search([("model", "=", "sale.order"), ("res_id", "=", so.id)], order="id"):
    tv = [(t.field_id.name, t.old_value_char, t.new_value_char) for t in m.tracking_value_ids]
    print("R   msg", m.date, m.message_type, (m.body or "")[:120].replace("\n", " "), tv)
cur.execute("""SELECT cd.Id, cd.Entidade, cd.Nome, cd.Data, cd.DataUltimaActualizacao, cd.TipoEntidade, cd.EntidadeFac, cd.EntidadeEntrega, cd.Utilizador FROM CabecDoc cd WHERE cd.TipoDoc='ECL' AND cd.Serie='2026' AND cd.NumDoc=427""")
cols = [d[0] for d in cur.description]
for r in cur.fetchall(): print("R Primavera:", dict(zip(cols, [str(x) for x in r])))
for code in ("CL0647", "CL0001"):
    p = env["res.partner"].sudo().with_context(active_test=False).search([("primavera_customer_code", "=", code)])
    print("R ficha", code, [(x.id, x.name, x.create_date, x.active) for x in p])
env.cr.execute("select id, name, state, partner_id from sale_order where partner_id = %s order by id", (so.partner_id.id,))
print("R ECLs do cliente Odoo actual:", env.cr.fetchall()[:20])
env.cr.rollback()
