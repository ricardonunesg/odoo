import copy, json
from unittest import mock
from odoo.addons.primavera_connector.models import primavera_connection as M
RES = []
def check(nome, cond, extra=""):
    RES.append(bool(cond))
    print("R", "PASS" if cond else "FAIL", "|", nome, ("| " + str(extra)) if extra else "", flush=True)

D = json.load(open("/out/p4_dados.json"))
api = D["api"]
c = env["primavera.connection"].browse(1)
P = env["res.partner"].sudo().with_context(active_test=False)
Log = env["primavera.sync.log"]
REAL_INACT = {"customer": set(), "supplier": {"FO0160", "FO0792"}}

def correr(tipo, codes, dados=None, inactivos=REAL_INACT):
    dados = dados or api
    with mock.patch.object(M.PrimaveraConnection, "_exists", lambda self, ep, strict=False: ep.rsplit("/", 1)[-1] in dados), \
         mock.patch.object(M.PrimaveraConnection, "_edita", lambda self, ep, strict=False: copy.deepcopy(dados.get(ep.rsplit("/", 1)[-1]))), \
         mock.patch.object(M.PrimaveraConnection, "_primavera_codigos_inactivos", lambda self: inactivos):
        ultimo = Log.search([], order="id desc", limit=1).id or 0
        c._import_partners(tipo, codes=codes)
        return Log.search([("message", "=like", "[estado]%"), ("id", ">", ultimo)]).mapped("message")

def ficha(campo, code):
    return P.search([(campo, "=", code)], limit=1)

cl = sorted(k for k in api if k.startswith("CL")); fo = sorted(k for k in api if k.startswith("FO"))
antes = {p.id: p.active for p in P.search(["|", ("primavera_customer_code", "in", cl), ("primavera_supplier_code", "in", fo)])}

# 1. Situação real (41 códigos): só os 2 anulados são arquivados
l1 = correr("customer", cl) + correr("supplier", fo)
arq = [p for p in P.search([("id", "in", list(antes))]) if antes[p.id] != p.active]
check("situação real: só FO0160 e FO0792 arquivados", sorted(p.primavera_supplier_code for p in arq) == ["FO0160", "FO0792"]
      and all(not p.active for p in arq), (l1, [(p.name, p.active) for p in arq]))
# 2. Segunda execução: nada muda
l2 = correr("customer", cl) + correr("supplier", fo)
check("segunda sincronização: nenhuma alteração de estado", not l2 and not [p for p in P.search([("id", "in", list(antes))]) if (p.id in [a.id for a in arq]) == p.active], l2)
# 3. Reactivação no Primavera
d3 = copy.deepcopy(api); d3["FO0160"]["Inactivo"] = False
l3 = correr("supplier", ["FO0160"], d3, {"customer": set(), "supplier": {"FO0792"}})
check("reactivado no Primavera → reactivado no Odoo", ficha("primavera_supplier_code", "FO0160").active, l3)
# 4. Ficha cliente+fornecedor
pid, clc, foc = D["partilhadas"][0]
d4 = copy.deepcopy(api); d4[foc]["Inactivo"] = True
correr("supplier", [foc], d4, {"customer": set(), "supplier": {foc}})
check("cliente+fornecedor: só o fornecedor anulado → continua activa", P.browse(pid).active)
d4[clc]["Inactivo"] = True
correr("customer", [clc], d4, {"customer": {clc}, "supplier": {foc}})
check("cliente+fornecedor: os dois anulados → arquivada", not P.browse(pid).active)
d4[clc]["Inactivo"] = False
correr("customer", [clc], d4, {"customer": set(), "supplier": {foc}})
check("cliente+fornecedor: cliente reactivado → reactivada", P.browse(pid).active)
d4[clc]["Inactivo"] = True
correr("customer", [clc], d4, None)
check("cliente+fornecedor: sem SQL não se mexe", P.browse(pid).active)
# 5. MARIN TRADING: anulado com o mesmo NIF não arquiva a ficha de outro código
marin = ficha("primavera_customer_code", "CL0063")
d5 = copy.deepcopy(api); d5["CL0027"]["Inactivo"] = True
correr("customer", ["CL0027"], d5, {"customer": {"CL0027"}, "supplier": set()})
marin.invalidate_recordset()
check("MARIN TRADING (encontrada pelo NIF) não é arquivada por causa do CL0027", marin.active, (marin.name, marin.primavera_customer_code))
# 6. Ficha ligada a utilizador do Odoo
f6 = ficha("primavera_supplier_code", "FO0160")
env["res.users"].sudo().create({"name": "Utilizador teste p4", "login": "teste_p4_estado", "partner_id": f6.id})
d6 = copy.deepcopy(api)
l6 = correr("supplier", ["FO0160"], d6, REAL_INACT)
avisos = Log.search_count([("state", "=", "warning"), ("message", "like", "ligada a um utilizador")])
check("ficha ligada a utilizador: não arquivada e fica aviso", f6.active and avisos >= 1, (l6, avisos))
# 7. Fusão pelo NIF Dedup num contacto CRM (sem códigos) com anulado novo
crm = P.create({"name": "Contacto CRM teste p4", "vat": "PT123456789", "is_company": True})
d7 = copy.deepcopy(api); novo = copy.deepcopy(api["FO0160"])
novo.update({"Fornecedor": "FO9999", "NumContribuinte": "123456789", "Pais": "PT", "Inactivo": True, "Nome": "X", "NomeFiscal": "X"})
d7["FO9999"] = novo
correr("supplier", ["FO9999"], d7, {"customer": set(), "supplier": {"FO9999"}})
crm.invalidate_recordset()
check("NIF Dedup funde anulado novo num contacto CRM → contacto NÃO é arquivado", crm.active and crm.primavera_supplier_code == "FO9999", (crm.active, crm.primavera_supplier_code))
# 8. Anulado novo sem fusão → criado e arquivado
n8 = copy.deepcopy(api["FO0160"]); n8.update({"Fornecedor": "FO9998", "NumContribuinte": "", "Inactivo": True, "Nome": "Y", "NomeFiscal": "Y"})
d8 = copy.deepcopy(api); d8["FO9998"] = n8
correr("supplier", ["FO9998"], d8, {"customer": set(), "supplier": {"FO9998"}})
f8 = ficha("primavera_supplier_code", "FO9998")
check("anulado novo (sem fusão) → criado já arquivado", f8 and not f8.active, (bool(f8), f8.active if f8 else None))
print("R TOTAL", sum(RES), "/", len(RES))
env.cr.rollback()
