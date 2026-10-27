import re
from collections import defaultdict, Counter
from difflib import SequenceMatcher
c = env["primavera.connection"].browse(1)
cur = c._sql_connection().cursor()
P = env["res.partner"].sudo().with_context(active_test=False)

def nucleo(vat):
    v = re.sub(r"[^A-Z0-9]", "", (vat or "").upper())
    return v[2:] if len(v) > 2 and v[:2].isalpha() and not v[2:3].isalpha() else v
def ficticio(vat):
    n = nucleo(vat)
    return (not n) or len(n) < 5 or len(set(n)) == 1 or n in ("123456789", "999999990")

prim = {}
for tab, chave, anul, tipo in (("Clientes", "Cliente", "ClienteAnulado", "customer"), ("Fornecedores", "Fornecedor", "FornecedorAnulado", "supplier")):
    cur.execute(f"SELECT {chave}, ISNULL(NomeFiscal, Nome), NumContrib, Pais, ISNULL({anul},0), DataUltimaActualizacao FROM {tab}")
    for cod, nome, nif, pais, an, dt in cur.fetchall():
        prim[(tipo, cod.strip())] = {"nome": (nome or "").strip(), "nif": (nif or "").strip(), "pais": (pais or "").strip(),
                                     "vat": c._format_vat(nif, pais) or "", "anulado": bool(an), "dt": str(dt)[:10]}
grupos = defaultdict(list)
for (tipo, cod), d in prim.items():
    if d["vat"] and not ficticio(d["vat"]):
        grupos[(tipo, nucleo(d["vat"]))].append(cod)
partilhados = {k: v for k, v in grupos.items() if len(v) > 1}
fict = Counter((t, d["vat"]) for (t, cod), d in prim.items() if d["vat"] and ficticio(d["vat"]))
print("R NIF fictícios no Primavera (tipo, NIF, nº de códigos):", sorted([(t, v, n) for (t, v), n in fict.items()], key=lambda x: -x[2])[:12], "| total códigos:", sum(fict.values()))
print("R NIF reais partilhados por vários códigos do MESMO tipo:", len(partilhados), sorted([(k[0], k[1], v, [prim[(k[0], x)]["nome"][:22] for x in v]) for k, v in partilhados.items()])[:12])

field = {"customer": "primavera_customer_code", "supplier": "primavera_supplier_code"}
odoo = {(t, p[field[t]]): p for t in field for p in P.search([(field[t], "!=", False)])}
falta = [k for k in prim if k not in odoo and k[1][:2] in ("CL", "FO")]
print("R códigos do Primavera sem ficha própria no Odoo:", len(falta))
for t, cod in sorted(falta):
    d = prim[(t, cod)]
    alvo = c._find_existing_partner(d["vat"]) if t == "customer" else P
    print("R   ", cod, d["nome"][:30], "| NIF", d["vat"], "| fictício" if ficticio(d["vat"]) else "", "| anulado" if d["anulado"] else "",
          "| alterado", d["dt"], "| cai na ficha:", (alvo.id, alvo.name, alvo.primavera_customer_code) if alvo else "-")

# fichas cliente+fornecedor com nomes muito diferentes
estranhas = []
for p in P.search([("primavera_customer_code", "!=", False), ("primavera_supplier_code", "!=", False)]):
    a = prim.get(("customer", p.primavera_customer_code), {}).get("nome", ""); b = prim.get(("supplier", p.primavera_supplier_code), {}).get("nome", "")
    r = SequenceMatcher(None, a.upper(), b.upper()).ratio()
    if r < 0.6:
        estranhas.append((p.id, p.primavera_customer_code, a[:28], p.primavera_supplier_code, b[:28], round(r, 2),
                          "NIF fictício" if ficticio(p.vat) else ""))
print("R fichas cliente+fornecedor com nomes diferentes (<60% parecidos):", len(estranhas), estranhas[:10])

# documentos ligados a ficha com código diferente da entidade do Primavera
cur.execute("""SELECT c.TipoDoc + '/' + c.Serie + '/' + CAST(c.NumDoc AS varchar), c.Entidade FROM CabecDoc c
               WHERE c.TipoDoc IN ('ECL','FA','FAT') AND c.Serie='2026'""")
ent = {r: (e or "").strip() for r, e in cur.fetchall()}
mal = []
for so in env["sale.order"].sudo().search([("primavera_ecl_ref", "like", "ECL/2026/%")]):
    if ent.get(so.primavera_ecl_ref) and so.partner_id.primavera_customer_code != ent[so.primavera_ecl_ref]:
        mal.append((so.primavera_ecl_ref, ent[so.primavera_ecl_ref], so.partner_id.primavera_customer_code, so.partner_id.name[:25]))
for m in env["account.move"].sudo().search([("primavera_ref", "!=", False)]):
    if ent.get(m.primavera_ref) and m.partner_id.primavera_customer_code != ent[m.primavera_ref]:
        mal.append((m.primavera_ref, ent[m.primavera_ref], m.partner_id.primavera_customer_code, m.partner_id.name[:25]))
print("R ECLs/faturas 2026 ligadas a ficha com outro código:", len(mal), mal[:10])

# ligações das fichas onde caem os códigos sem ficha
for pid in sorted({c._find_existing_partner(prim[k]["vat"]).id for k in falta if k[0] == "customer"} - {False}):
    p = P.browse(pid)
    n_track = env["mail.tracking.value"].sudo().search_count([("mail_message_id.model", "=", "res.partner"), ("mail_message_id.res_id", "=", pid)])
    print("R ficha", pid, p.name, p.primavera_customer_code, p.primavera_supplier_code, "| NIF", p.vat,
          "| leads", env["crm.lead"].sudo().with_context(active_test=False).search_count([("partner_id", "=", pid)]),
          "| vendas", env["sale.order"].sudo().search_count([("partner_id", "=", pid)]),
          "| faturas", env["account.move"].sudo().search_count([("partner_id", "=", pid)]),
          "| documentos", sum(env[m].sudo().search_count([("fatura_id.partner_id", "=", pid)]) for m in ("packing.list", "declaracao.lote", "boletim.analises")),
          "| alterações no histórico", n_track)
# NIF fictícios guardados em fichas do Odoo com código
print("R fichas no Odoo com NIF fictício:", [(p.id, p.name[:22], p.vat, p.primavera_customer_code, p.primavera_supplier_code) for p in P.search([("vat", "!=", False)]) if ficticio(p.vat) and (p.primavera_customer_code or p.primavera_supplier_code)][:10])
