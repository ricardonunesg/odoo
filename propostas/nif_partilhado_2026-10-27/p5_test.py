import copy, json
from unittest import mock
from odoo.addons.primavera_connector.models import primavera_connection as M
from odoo.addons.mirazeite_partner_nif_dedup.models import res_partner as ND
RES = []
def check(nome, cond, extra=""):
    RES.append(bool(cond))
    print("R", "PASS" if cond else "FAIL", "|", nome, ("| " + str(extra)) if extra else "", flush=True)

assert hasattr(M, "vat_ficticio") and hasattr(ND, "vat_ficticio"), "código novo não carregado"
api = json.load(open("/out/p5_api.json"))
c = env["primavera.connection"].browse(1)
P = env["res.partner"].sudo().with_context(active_test=False)
TV = env["mail.tracking.value"].sudo()

def correr(tipo, codes, dados=None):
    dados = dados or api
    with mock.patch.object(M.PrimaveraConnection, "_exists", lambda self, ep, strict=False: ep.rsplit("/", 1)[-1] in dados), \
         mock.patch.object(M.PrimaveraConnection, "_edita", lambda self, ep, strict=False: copy.deepcopy(dados.get(ep.rsplit("/", 1)[-1]))), \
         mock.patch.object(M.PrimaveraConnection, "_primavera_codigos_inactivos", lambda self: {"customer": set(), "supplier": {"FO0160", "FO0792"}}):
        c._import_partners(tipo, codes=codes)

def mapa():
    return {p.id: (p.primavera_customer_code, p.primavera_supplier_code, p.name, p.vat, p.active) for p in P.search([])}
def hist(ids):
    return TV.search_count([("mail_message_id.model", "=", "res.partner"), ("mail_message_id.res_id", "in", ids)])
def nome_prim(code):
    d = api[code]; return (d.get("NomeFiscal") or d.get("Nome") or "").strip()

ATINGIDAS = {1754: "CL0063", 1841: "CL0128", 1851: "CL0137", 1909: "CL0181", 2200: "CL0760"}
SEM_FICHA = ["CL0027", "CL0056", "CL0062", "CL0109", "CL0119", "CL0171", "CL0455"]
cl = sorted(k for k in api if k.startswith("CL")); fo = sorted(k for k in api if k.startswith("FO"))
m0 = mapa(); h0 = hist(list(ATINGIDAS))

# 1. Volta completa (por ordem, como à noite)
correr("customer", cl); correr("supplier", fo)
m1 = mapa()
novas = {cod: P.search([("primavera_customer_code", "=", cod)]) for cod in SEM_FICHA}
check("os 7 códigos têm agora ficha própria", all(len(f) == 1 and f.id not in m0 for f in novas.values()),
      {k: (v.id, v.name[:25]) for k, v in novas.items()})
check("cada ficha nova tem o nome do seu código no Primavera", all(novas[k].name == nome_prim(k) for k in SEM_FICHA),
      [(k, novas[k].name[:20], nome_prim(k)[:20]) for k in SEM_FICHA if novas[k].name != nome_prim(k)])
check("as 5 fichas atingidas mantêm o seu código e o seu nome",
      all(m1[i][0] == cod and m1[i][2] == nome_prim(cod) for i, cod in ATINGIDAS.items()), {i: m1[i][:3] for i in ATINGIDAS})
check("nenhuma alteração falsa no histórico das 5 fichas", hist(list(ATINGIDAS)) == h0, (h0, hist(list(ATINGIDAS))))
outras = [i for i in m0 if m0[i][:2] != m1[i][:2] and i not in ATINGIDAS]
check("nenhuma outra ficha mudou de código", not outras, [(i, m0[i][:3], m1[i][:3]) for i in outras][:5])

# 2. Repetir: nada muda
h1 = hist(list(m0)); correr("customer", cl); correr("supplier", fo); m2 = mapa()
check("segunda volta completa: nenhuma ficha nova nem alterada", m2 == m1 and hist(list(m0)) == h1, len(m2) - len(m1))

# 3. Incremental só do CL0027
correr("customer", ["CL0027"])
check("incremental do CL0027 só mexe na ficha dele (MARIN intacta)", mapa() == m2 and P.browse(1754).name == nome_prim("CL0063"))

def nova_resposta(cod, nif, pais, nome):
    d = copy.deepcopy(api["CL0063"]); d.update({"Cliente": cod, "NumContribuinte": nif, "NumContrib": nif, "Pais": pais, "Nome": nome, "NomeFiscal": nome})
    dd = copy.deepcopy(api); dd[cod] = d; return dd

# 4. Contacto do CRM com lead é aproveitado e mantém a lead
crm = P.create({"name": "Empresa CRM teste p5", "vat": "PT123456789", "is_company": True})
lead = env["crm.lead"].sudo().create({"name": "Lead teste p5", "partner_id": crm.id})
correr("customer", ["CL9001"], nova_resposta("CL9001", "123456789", "PT", "EMPRESA CRM TESTE P5 LDA"))
crm.invalidate_recordset(); lead.invalidate_recordset()
check("contacto CRM aproveitado (recebe o código) e mantém a lead", crm.primavera_customer_code == "CL9001" and lead.partner_id == crm
      and P.search_count([("primavera_customer_code", "=", "CL9001")]) == 1, (crm.primavera_customer_code, lead.partner_id.id))

# 5. Empresa CRM + contacto dela (NIF herdado): fusão vai para a empresa
emp = P.create({"name": "Cooperativa teste p5", "vat": "PT987654322", "is_company": True})
pessoa = P.create({"name": "Pessoa da cooperativa p5", "parent_id": emp.id})
correr("customer", ["CL9002"], nova_resposta("CL9002", "987654322", "PT", "COOPERATIVA TESTE P5"))
emp.invalidate_recordset(); pessoa.invalidate_recordset()
check("empresa + contacto com o mesmo NIF: código vai para a empresa, não para a pessoa",
      emp.primavera_customer_code == "CL9002" and not pessoa.primavera_customer_code, (pessoa.vat, emp.primavera_customer_code, pessoa.primavera_customer_code))

# 6. Duas empresas CRM independentes com o mesmo NIF: não funde
a = P.create({"name": "Empresa A p5", "vat": "PT501964843", "is_company": True})
b = P.create({"name": "Empresa B p5", "vat": "PT501964843", "is_company": True})
correr("customer", ["CL9003"], nova_resposta("CL9003", "501964843", "PT", "EMPRESA C P5"))
f6 = P.search([("primavera_customer_code", "=", "CL9003")])
check("duas candidatas com o mesmo NIF: não funde, cria ficha nova", len(f6) == 1 and f6 not in (a | b)
      and not a.primavera_customer_code and not b.primavera_customer_code, f6.ids)

# 7. NIF fictício: não funde
fic = P.create({"name": "Contacto MZ p5", "vat": "MZ0", "is_company": True})
correr("customer", ["CL9004"], nova_resposta("CL9004", "0", "MZ", "OUTRA EMPRESA MZ P5"))
f7 = P.search([("primavera_customer_code", "=", "CL9004")])
check("NIF fictício: não funde com o contacto que tem o mesmo 'MZ0'", len(f7) == 1 and f7 != fic and not fic.primavera_customer_code, f7.ids)

# 8. Criação pela importação de uma ECL (código sem ficha, NIF partilhado)
env.cr.execute("SAVEPOINT p5_ecl")
P.search([("primavera_customer_code", "=", "CL0455")]).write({"primavera_customer_code": False})
vals = c._partner_vals_from_api(api["CL0455"], "customer", "primavera_customer_code", "customer_rank",
                                env.ref("primavera_connector.partner_category_primavera_customer"))
c._safe_create_partner(P, vals)
f8 = P.search([("primavera_customer_code", "=", "CL0455")])
check("ECL de um código sem ficha (NIF de outro cliente): cria ficha própria, não toca na INJOPET CL0760",
      len(f8) == 1 and f8.id != 2200 and P.browse(2200).primavera_customer_code == "CL0760", (f8.ids, P.browse(2200).primavera_customer_code))
env.cr.execute("ROLLBACK TO SAVEPOINT p5_ecl")
print("R TOTAL", sum(RES), "/", len(RES))
env.cr.rollback()
