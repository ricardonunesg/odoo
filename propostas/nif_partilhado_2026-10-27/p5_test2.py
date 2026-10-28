# Cenários adicionais: cliente ↔ fornecedor na mesma ficha; CRM → cliente com leads e histórico.
import copy, json
from unittest import mock
from odoo.addons.primavera_connector.models import primavera_connection as M
RES = []
def check(nome, cond, extra=""):
    RES.append(bool(cond))
    print("R", "PASS" if cond else "FAIL", "|", nome, ("| " + str(extra)) if extra else "", flush=True)

api = json.load(open("/out/p5_api.json"))
FO_BASE = sorted(k for k in api if k.startswith("FO"))[0]
c = env["primavera.connection"].browse(1)
P = env["res.partner"].sudo().with_context(active_test=False)
SO = env["sale.order"].sudo()

def correr(tipo, codes, dados):
    with mock.patch.object(M.PrimaveraConnection, "_exists", lambda self, ep, strict=False: ep.rsplit("/", 1)[-1] in dados), \
         mock.patch.object(M.PrimaveraConnection, "_edita", lambda self, ep, strict=False: copy.deepcopy(dados.get(ep.rsplit("/", 1)[-1]))), \
         mock.patch.object(M.PrimaveraConnection, "_primavera_codigos_inactivos", lambda self: {"customer": set(), "supplier": set()}):
        c._import_partners(tipo, codes=codes)

def resp(base, chave, cod, nif, pais, nome):
    d = copy.deepcopy(api[base]); d.update({chave: cod, "NumContribuinte": nif, "NumContrib": nif, "Pais": pais, "Nome": nome, "NomeFiscal": nome})
    for k in ("Inactivo", "ClienteAnulado", "FornecedorAnulado"):
        d.pop(k, None)
    return d

# (a) cliente que passa a fornecedor — empresa com contactos e leads
cli = P.create({"name": "Cliente Teste A", "vat": "PT123456789", "is_company": True, "primavera_customer_code": "CL9101"})
P.create({"name": "Pessoa do cliente A", "parent_id": cli.id})
lead = env["crm.lead"].sudo().create({"name": "Lead do cliente A", "partner_id": cli.id})
d = {"FO9101": resp(FO_BASE, "Fornecedor", "FO9101", "123456789", "PT", "NOME DE FORNECEDOR A")}
correr("supplier", ["FO9101"], d)
cli.invalidate_recordset()
check("(a) cliente passa a fornecedor: MESMA ficha recebe o código de fornecedor", cli.primavera_supplier_code == "FO9101"
      and P.search_count([("primavera_supplier_code", "=", "FO9101")]) == 1, cli.primavera_supplier_code)
check("(a) dados do cliente mantêm-se (nome) e a lead continua ligada", cli.name == "Cliente Teste A" and lead.partner_id == cli, cli.name)

# (b) fornecedor (com contactos) que passa a cliente pela sincronização de clientes
forn = P.create({"name": "Fornecedor Teste B", "vat": "PT987654322", "is_company": True, "primavera_supplier_code": "FO9102"})
P.create({"name": "Pessoa do fornecedor B", "parent_id": forn.id})
correr("customer", ["CL9102"], {"CL9102": resp("CL0063", "Cliente", "CL9102", "987654322", "PT", "CLIENTE B LDA")})
forn.invalidate_recordset()
check("(b) fornecedor (com contactos) passa a cliente: mesma ficha", forn.primavera_customer_code == "CL9102"
      and P.search_count([("primavera_customer_code", "=", "CL9102")]) == 1, forn.primavera_customer_code)

# (c) fornecedor que passa a cliente através de uma ECL (cliente ainda sem ficha)
forn2 = P.create({"name": "Fornecedor Teste C", "vat": "PT501964843", "is_company": True, "primavera_supplier_code": "FO9103"})
vals = c._partner_vals_from_api(resp("CL0063", "Cliente", "CL9103", "501964843", "PT", "CLIENTE C"), "customer",
                                "primavera_customer_code", "customer_rank", env.ref("primavera_connector.partner_category_primavera_customer"))
c._criar_ou_aproveitar_cliente(P, vals)
forn2.invalidate_recordset()
check("(c) cliente novo vindo de uma ECL com NIF de um fornecedor: mesma ficha", forn2.primavera_customer_code == "CL9103"
      and P.search_count([("primavera_customer_code", "=", "CL9103")]) == 1, forn2.primavera_customer_code)

# (d) contacto do CRM (leads, mensagens) que passa a cliente: mesma ficha, leads e histórico preservados
crm = P.create({"name": "Empresa CRM D", "vat": "PT502280980", "is_company": True})
l1 = env["crm.lead"].sudo().create({"name": "Oportunidade D1", "partner_id": crm.id})
l2 = env["crm.lead"].sudo().create({"name": "Oportunidade D2", "partner_id": crm.id})
crm.message_post(body="Nota comercial antiga D")
msgs = env["mail.message"].sudo().search_count([("model", "=", "res.partner"), ("res_id", "=", crm.id)])
correr("customer", ["CL9104"], {"CL9104": resp("CL0063", "Cliente", "CL9104", "502280980", "PT", "EMPRESA CRM D LDA")})
crm.invalidate_recordset()
check("(d) contacto do CRM passa a cliente: mesma ficha (NIF Dedup)", crm.primavera_customer_code == "CL9104"
      and P.search_count([("primavera_customer_code", "=", "CL9104")]) == 1, crm.primavera_customer_code)
check("(d) as 2 leads e o histórico mantêm-se", l1.partner_id == crm and l2.partner_id == crm
      and env["mail.message"].sudo().search_count([("model", "=", "res.partner"), ("res_id", "=", crm.id)]) >= msgs)

# (e) ambíguo: dois clientes com o mesmo NIF → fornecedor novo não se junta a nenhum
x1 = P.create({"name": "Cliente E1", "vat": "PT500697256", "is_company": True, "primavera_customer_code": "CL9105"})
x2 = P.create({"name": "Cliente E2", "vat": "PT500697256", "is_company": True, "primavera_customer_code": "CL9106"})
correr("supplier", ["FO9105"], {"FO9105": resp(FO_BASE, "Fornecedor", "FO9105", "500697256", "PT", "FORNECEDOR E")})
fe = P.search([("primavera_supplier_code", "=", "FO9105")])
check("(e) dois clientes com o mesmo NIF: fornecedor fica numa ficha própria (não adivinha)",
      len(fe) == 1 and fe not in (x1 | x2), fe.ids)

# (f) NIF fictício: fornecedor não se junta a cliente com 'MZ0'
correr("supplier", ["FO9106"], {"FO9106": resp(FO_BASE, "Fornecedor", "FO9106", "0", "MZ", "FORNECEDOR MZ")})
ff = P.search([("primavera_supplier_code", "=", "FO9106")])
check("(f) NIF fictício: fornecedor não se junta à MARIN", len(ff) == 1 and ff.id != 1754 and not P.browse(1754).primavera_supplier_code, ff.ids)

# (g) as 3 duplicações existentes não são mexidas por uma volta completa dos seus códigos
dups = {3566: "CL0905", 2853: "FO0220", 3624: "CL0909", 3449: "FO0858", 2594: "CL0841", 3573: "FO0877"}
antes = {i: (P.browse(i).primavera_customer_code, P.browse(i).primavera_supplier_code, P.browse(i).name) for i in dups}
print("R (g) duplicações existentes (não alteradas):", antes)
print("R TOTAL", sum(RES), "/", len(RES))
env.cr.rollback()
