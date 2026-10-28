# Correcção das 24 faturas com IVA errado: reimportação com o conector actual, sem notificações.
# MODO (no topo, preenchido ao correr): "ensaio-protegido", "ensaio-sem-proteccao" ou "producao".
import copy, json
from unittest import mock
from odoo.addons.primavera_connector.models import primavera_connection as M
assert MODO in ("ensaio-protegido", "ensaio-sem-proteccao", "producao")
AFECTADAS = ["FA/2026/170", "FA/2026/172", "FA/2026/174", "FA/2026/175", "FA/2026/176", "FA/2026/180", "FA/2026/181", "FA/2026/183",
             "FA/2026/184", "FA/2026/185", "FA/2026/186", "FA/2026/187", "FA/2026/189", "FA/2026/193", "FA/2026/197", "FA/2026/198",
             "FA/2026/200", "FAT/2026/192", "FAT/2026/194", "FAT/2026/195", "FAT/2026/201", "FAT/2026/202", "FAT/2026/205", "FAT/2026/206"]
def R(*a): print("R", *a, flush=True)
patches = []
if MODO.startswith("ensaio"):
    D = json.load(open("/out/iva_data.json"))
    def edita(self, ep, strict=False):
        p = ep.split("/")
        if "/Vendas/Docs/Edita/" in ep:
            return copy.deepcopy(D["api"].get(f"{p[-3]}/{p[-2]}/{p[-1]}"))
        if "/Base/Artigos/Edita/" in ep:
            return copy.deepcopy(D["art"].get(p[-1]))
        return None
    patches += [mock.patch.object(M.PrimaveraConnection, "_edita", edita),
                mock.patch.object(M.PrimaveraConnection, "_sql_connection", lambda self: None)]
if MODO != "ensaio-sem-proteccao":
    # Só neste processo: não mexer na ligação fatura ↔ ECL (fica exactamente como está) e,
    # por isso, não criar tarefas "Completar processo" nem as respectivas notificações
    patches.append(mock.patch.object(M.PrimaveraConnection, "_link_fatura_to_ecl", lambda self, move, fatura_name, origens: None))
    patches.append(mock.patch.object(M.PrimaveraConnection, "_criar_todos_ecl", lambda self, ecl_so, fatura_name: None))
for p in patches:
    p.start()
ctx = {} if MODO == "ensaio-sem-proteccao" else dict(tracking_disable=True, mail_notrack=True, mail_create_nolog=True, mail_auto_subscribe_no_notify=True)
c = env["primavera.connection"].browse(1).with_context(**ctx)
AM = env["account.move"].sudo()

def q1(sql, args=()):
    env.cr.execute(sql, args); return env.cr.fetchone()[0]
def foto():
    out = {}
    for m in AM.search([("primavera_ref", "=like", "F%/2026/%")]):
        out[m.primavera_ref] = (m.id, m.state, round(m.amount_untaxed, 2), round(m.amount_tax, 2), round(m.amount_total, 2),
                                m.partner_id.id, m.ecl_sale_order_id.id, tuple(sorted(m.invoice_line_ids.ids)))
    return out
def ligacoes():
    env.cr.execute("""select 'PL', id, fatura_id from packing_list union all select 'BA', id, fatura_id from boletim_analises
      union all select 'CS', id, fatura_id from certificado_salubridade union all select 'CQ', id, fatura_id from certificado_qualidade
      union all select 'DL', id, fatura_id from declaracao_lote""")
    a = sorted(env.cr.fetchall())
    env.cr.execute("select id, primavera_fatura_refs from sale_order where primavera_fatura_refs is not null order by id")
    return a, env.cr.fetchall()
cont = lambda: dict(mensagens=q1("select coalesce(max(id),0) from mail_message"), notif=q1("select coalesce(max(id),0) from mail_notification"),
                    emails=q1("select coalesce(max(id),0) from mail_mail"), tarefas=q1("select coalesce(max(id),0) from project_task"),
                    actividades=q1("select coalesce(max(id),0) from mail_activity"), faturas=q1("select count(*) from account_move"),
                    parceiros=q1("select count(*) from res_partner"))
f0, l0, c0 = foto(), ligacoes(), cont()
R("antes:", {r: f0[r][3] for r in AFECTADAS[:4]}, "… | FAT/2026/185:", f0["FAT/2026/185"][1:5])
for ref in AFECTADAS:
    assert f0[ref][1] == "draft", ref
    t, s, n = ref.split("/")
    c._import_faturas_doc(t, s, int(n) - 1, 1, 1, None)
f1, l1, c1 = foto(), ligacoes(), cont()
novos = {k: q1(f"select count(*) from {t} where id > %s", (c0[k],)) for k, t in (("mensagens", "mail_message"), ("notif", "mail_notification"), ("emails", "mail_mail"), ("tarefas", "project_task"), ("actividades", "mail_activity"))}
R("1. faturas no Odoo antes/depois:", c0["faturas"], c1["faturas"], "| parceiros:", c0["parceiros"], c1["parceiros"], "| mesmas fichas (id) nas 24:", all(f0[r][0] == f1[r][0] for r in AFECTADAS))
R("2. criados durante a reimportação:", novos)
if novos["mensagens"]:
    env.cr.execute("select model, message_type, count(*) from mail_message where id > %s group by 1,2", (c0["mensagens"],)); R("   mensagens:", env.cr.fetchall())
R("3. diferenças nas ligações — documentos:", sorted(set(l0[0]) ^ set(l1[0]))[:10], "| refs ECL:", [(a, b) for a, b in zip(sorted(l0[1]), sorted(l1[1])) if a != b][:10], len(l0[1]), len(l1[1]))
R("3. ligações a documentos (PL/BA/CS/CQ/DL) e refs nas ECLs iguais:", l0 == l1, "| ECL ligada igual nas 24:", all(f0[r][6] == f1[r][6] for r in AFECTADAS))
outras = [k for k in f0 if k not in AFECTADAS and f0[k] != f1.get(k)]
R("4. outras faturas alteradas:", outras, "| FAT/2026/185 igual:", f0["FAT/2026/185"] == f1["FAT/2026/185"])
R("   as 24 — IVA antes → depois:", [(r, f0[r][3], f1[r][3]) for r in AFECTADAS])
if MODO.startswith("ensaio"):
    okv = [r for r in AFECTADAS if abs(f1[r][3] - D["H"][r]["iva"]) <= 0.005 and abs(f1[r][4] - D["H"][r]["total"]) <= 0.05]
    R("   iguais ao Primavera (IVA exacto, total ≤ 0,05 €):", len(okv), "/ 24", sorted(set(AFECTADAS) - set(okv)))
    env.cr.rollback(); R("FIM ensaio (desfeito)")
else:
    env.cr.commit(); R("FIM produção (gravado)")
for p in patches:
    p.stop()
