PT = env["product.template"].sudo()
arch = PT.get_views([(False, "form")])["views"]["form"]["arch"]
print("R reversão: ficha do artigo abre:", "primavera_code" in arch, "| sem campos novos:", "primavera_peso_liquido" not in arch)
env.cr.execute("select count(*) from ir_model_fields where name in ('primavera_peso_liquido','primavera_aviso_pesos')")
print("R campos novos registados após reversão:", env.cr.fetchone()[0])
env.cr.execute("select column_name from information_schema.columns where table_name='product_template' and column_name like 'primavera_%%'")
print("R colunas na tabela (ficam, sem uso):", [r[0] for r in env.cr.fetchall()])
pl = env["packing.list"].sudo().browse(36); pl.action_load_fatura_lines(); print("R PL recarrega com código antigo: líquido", pl.total_peso_liquido)
env.cr.rollback()
