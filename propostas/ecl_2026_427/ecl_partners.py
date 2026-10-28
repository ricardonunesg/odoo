for pid in (1726, 2396):
    p = env["res.partner"].sudo().browse(pid)
    print("R", pid, p.name, "| comercial:", p.user_id.name, "| país:", p.country_id.code, "| tipo docs:", p.export_doc_type, "| docs exigidos:", p.required_doc_ids.mapped("name"),
          "| posição fiscal:", p.property_account_position_id.name, "| tabela:", p.property_product_pricelist.name, "| pagamento:", p.property_payment_term_id.name)
so = env["sale.order"].sudo().browse(515)
print("R ECL 427 hoje: comercial", so.user_id.name, "| equipa", so.team_id.name, "| posição fiscal", so.fiscal_position_id.name, "| tabela", so.pricelist_id.name, "| docs:", so.ecl_doc_line_ids.mapped("doc_type_id.name"))
env.cr.rollback()
