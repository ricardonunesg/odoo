from odoo.addons.primavera_connector.models import primavera_connection as M
assert hasattr(M.PrimaveraConnection, "_ecl_trocar_cliente")
c = env["primavera.connection"].browse(1)
so = env["sale.order"].sudo().search([("primavera_ecl_ref", "=", "ECL/2026/427")])
def q1(sql, a=()):
    env.cr.execute(sql, a); return env.cr.fetchone()[0]
m0 = {t: q1(f"select coalesce(max(id),0) from {t}") for t in ("mail_message", "mail_notification", "mail_mail", "project_task", "mail_activity")}
a = (so.partner_id.name, so.state, so.stage_id.name, so.fiscal_position_id.name, so.pricelist_id.name, so.payment_term_id.name, so.user_id.name, so.team_id.name, so.ecl_doc_line_ids.ids, len(so.message_ids))
c._resync_single_ecl("ECL/2026/427", strict=True)
so.invalidate_recordset()
b = (so.partner_id.name, so.state, so.stage_id.name, so.fiscal_position_id.name, so.pricelist_id.name, so.payment_term_id.name, so.user_id.name, so.team_id.name, so.ecl_doc_line_ids.ids, len(so.message_ids))
novos = {t: q1(f"select count(*) from {t} where id > %s", (m0[t],)) for t in m0}
env.cr.execute("select model, res_id, message_type, left(body, 140) from mail_message where id > %s", (m0["mail_message"],))
msgs = env.cr.fetchall()
env.cr.commit()
print("R antes :", a)
print("R depois:", b, "| faturação:", so.partner_invoice_id.name, "| entrega:", so.partner_shipping_id.name, "| código:", so.partner_id.primavera_customer_code)
print("R criados durante a correcção:", novos, msgs)
