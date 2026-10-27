from collections import Counter
c = env["primavera.connection"].browse(1)
cur = c._sql_connection().cursor()
P = env["res.partner"].sudo().with_context(active_test=False)
prim = {}
for tab, chave, anul, campo in (("Clientes", "Cliente", "ClienteAnulado", "primavera_customer_code"),
                                ("Fornecedores", "Fornecedor", "FornecedorAnulado", "primavera_supplier_code")):
    cur.execute(f"SELECT {chave}, Nome, ISNULL({anul},0), DataUltimaActualizacao FROM {tab}")
    for cod, nome, a, dt in cur.fetchall():
        prim[(campo, cod.strip())] = (bool(a), nome, dt)
anulados = {k: v for k, v in prim.items() if v[0]}
print("R anulados no Primavera:", [(k[1], v[1], str(v[2])[:10]) for k, v in anulados.items()])
# divergências em ambos os sentidos
div = Counter(); ex = []
for p in P.search(["|", ("primavera_customer_code", "!=", False), ("primavera_supplier_code", "!=", False)]):
    roles = []
    for campo in ("primavera_customer_code", "primavera_supplier_code"):
        if p[campo]:
            roles.append(prim.get((campo, p[campo]), (None,))[0])
    if None in roles:
        div["código no Odoo que não existe no Primavera"] += 1; ex.append((p.id, p.name, p.primavera_customer_code, p.primavera_supplier_code)); continue
    todos_anulados = all(roles)
    if todos_anulados and p.active:
        div["anulado no Primavera e ACTIVO no Odoo"] += 1
    elif not todos_anulados and not p.active:
        div["activo no Primavera e ARQUIVADO no Odoo"] += 1; ex.append((p.id, p.name))
    elif any(roles) and not todos_anulados:
        div["cliente+fornecedor com um papel anulado e outro activo"] += 1; ex.append((p.id, p.name, p.primavera_customer_code, p.primavera_supplier_code))
    else:
        div["coerente"] += 1
print("R estado no Odoo vs Primavera:", dict(div), ex[:8])
print("R fichas com código de cliente E de fornecedor:", P.search_count([("primavera_customer_code", "!=", False), ("primavera_supplier_code", "!=", False)]))
# ligações das fichas dos anulados
for (campo, cod), v in anulados.items():
    for p in P.search([(campo, "=", cod)]):
        lig = {
            "utilizadores": env["res.users"].sudo().with_context(active_test=False).search_count([("partner_id", "=", p.id)]),
            "leads/oport.": env["crm.lead"].sudo().with_context(active_test=False).search_count([("partner_id", "=", p.id)]),
            "vendas/ECLs": env["sale.order"].sudo().search_count([("partner_id", "=", p.id)]),
            "faturas": env["account.move"].sudo().search_count([("partner_id", "=", p.id)]),
            "compras": env["purchase.order"].sudo().search_count([("partner_id", "=", p.id)]) if "purchase.order" in env else "-",
            "contactos filhos": P.search_count([("parent_id", "=", p.id)]),
            "reclamações": sum(env[m].sudo().search_count([(f, "=", p.id)]) for m, f in (("qualidade.cliente", "partner_id"), ("qualidade.fornecedor", "partner_id")) if m in env and f in env[m]._fields),
            "formulários": sum(env[m].sudo().search_count([(f, "=", p.id)]) for m in ("form.cliente", "form.fornecedor") if m in env for f in env[m]._fields if env[m]._fields[f].comodel_name == "res.partner" and env[m]._fields[f].type == "many2one"),
            "seguidor de registos": env["mail.followers"].sudo().search_count([("partner_id", "=", p.id)]),
        }
        print("R ficha", p.id, p.name, "| cliente", p.primavera_customer_code, "| fornecedor", p.primavera_supplier_code, "| activa", p.active, "|", lig)
# API devolve o campo de anulação?
for cod in [k[1] for k in anulados if k[0] == "primavera_supplier_code"][:1]:
    d = c._edita(f"/v2/Base/Fornecedores/Edita/{cod}", strict=True)
    print("R API fornecedor", cod, "FornecedorAnulado =", d.get("FornecedorAnulado"))
cur.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='Fornecedores' AND COLUMN_NAME IN ('VersaoUltAct','DataUltimaActualizacao','DataCriacao')")
print("R colunas de alteração em Fornecedores:", [r[0] for r in cur.fetchall()])
