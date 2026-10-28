# ECL/2026/427 — ensaio em cópia isolada (corre igual com o código de produção e com a proposta).
import copy, json
from unittest import mock
from odoo.addons.primavera_connector.models import primavera_connection as M
D = json.load(open("/out/p6_data.json"))
c = env["primavera.connection"].browse(1)
SO = env["sale.order"].sudo().with_context(active_test=False)
PROPOSTA = hasattr(M.PrimaveraConnection, "_ecl_trocar_cliente")
RES = []
def R(*a): print("R", *a, flush=True)
def check(nome, cond, extra=""):
    RES.append(bool(cond)); R("PASS" if cond else "FAIL", "|", nome, ("| " + str(extra)) if extra else "")
R("versão:", "PROPOSTA" if PROPOSTA else "produção actual")
API = copy.deepcopy(D["ecl"])
def edita(self, ep, strict=False):
    p = ep.split("/")
    if "/Vendas/Docs/Edita/" in ep:
        return copy.deepcopy(API.get(f"ECL/{p[-2]}/{p[-1]}"))
    if "/Base/Artigos/Edita/" in ep:
        return copy.deepcopy(D["art"].get(p[-1]))
    return None
for p in [mock.patch.object(M.PrimaveraConnection, "_edita", edita), mock.patch.object(M.PrimaveraConnection, "_sql_connection", lambda self: None)]:
    p.start()
def q1(sql, a=()):
    env.cr.execute(sql, a); return env.cr.fetchone()[0]
def foto(so):
    return dict(partner=so.partner_id.id, inv=so.partner_invoice_id.id, ship=so.partner_shipping_id.id, user=so.user_id.id, team=so.team_id.id,
                fpos=so.fiscal_position_id.id, pl=so.pricelist_id.id, pay=so.payment_term_id.id, state=so.state, stage=so.stage_id.id,
                docs=tuple(so.ecl_doc_line_ids.ids), lines=tuple((l.product_id.id, l.product_uom_qty, l.price_unit) for l in so.order_line),
                total=so.amount_total, msgs=tuple(so.message_ids.ids), seguidores=tuple(sorted(so.message_follower_ids.mapped("partner_id").ids)),
                faturas=so.primavera_fatura_refs)
COREYSA = env["res.partner"].sudo().search([("primavera_customer_code", "=", "CL0647")])
so = SO.search([("primavera_ecl_ref", "=", "ECL/2026/427")])
mx = lambda: dict(msg=q1("select coalesce(max(id),0) from mail_message"), notif=q1("select coalesce(max(id),0) from mail_notification"), mail=q1("select coalesce(max(id),0) from mail_mail"), task=q1("select coalesce(max(id),0) from project_task"))
def novos(m0):
    return dict(mensagens=q1("select count(*) from mail_message where id > %s", (m0["msg"],)), notificacoes=q1("select count(*) from mail_notification where id > %s", (m0["notif"],)),
                emails=q1("select count(*) from mail_mail where id > %s", (m0["mail"],)), tarefas=q1("select count(*) from project_task where id > %s", (m0["task"],)))

# E1 — re-sincronizar a ECL/2026/427
a = foto(so); m0 = mx()
c._resync_single_ecl("ECL/2026/427"); so.invalidate_recordset()
b = foto(so); n1 = novos(m0)
R("E1 cliente:", env["res.partner"].browse(a["partner"]).name, "→", so.partner_id.name, "| novos:", n1)
nota = so.message_ids.filtered(lambda m: m.id > m0["msg"])
R("E1 nota no histórico:", [(m.message_type, m.subtype_id.name, m.body) for m in nota])
if PROPOSTA:
    check("E1 ECL/2026/427 passa para a COREYSA (cliente, faturação e entrega)", b["partner"] == b["inv"] == b["ship"] == COREYSA.id)
    check("E1 comercial, equipa, posição fiscal, tabela, pagamento, estado e etapa iguais", all(a[k] == b[k] for k in ("user", "team", "fpos", "pl", "pay", "state", "stage")))
    check("E1 documentos de exportação, linhas, total, seguidores e faturas iguais", all(a[k] == b[k] for k in ("docs", "lines", "total", "seguidores", "faturas")))
    check("E1 histórico antigo intacto + 1 registo da correcção", set(a["msgs"]) <= set(b["msgs"]) and len(b["msgs"]) == len(a["msgs"]) + 1)
    check("E1 sem notificações, emails nem tarefas", n1["notificacoes"] == 0 and n1["emails"] == 0 and n1["tarefas"] == 0, n1)
else:
    check("E1 (produção actual) a ECL continua com o cliente errado", b["partner"] == a["partner"])

# E2 — volta completa das ECLs em curso: só a 427 muda de cliente, sem notificações
ecls = SO.search(c._ecl_resync_domain())
antes = {s.id: s.partner_id.id for s in ecls}
m2 = mx(); n = c._resync_ecls_full(); n2 = novos(m2)
mud = [s.primavera_ecl_ref for s in ecls if s.partner_id.id != antes[s.id]]
R("E2 volta completa:", n, "ECLs | mudaram de cliente:", mud, "| novos:", n2)
check("E2 nenhuma outra ECL muda de cliente", mud == [], mud)
check("E2 sem notificações, emails nem tarefas", n2["notificacoes"] == 0 and n2["emails"] == 0 and n2["tarefas"] == 0, n2)

# E3 — troca simulada numa ECL activa sem faturas
s3 = SO.search([("primavera_ecl_ref", "in", list(API)), ("state", "=", "sale"), ("primavera_fatura_refs", "=", False), ("invoice_ids", "=", False)], limit=1)
outro = env["res.partner"].sudo().search([("primavera_customer_code", "!=", False), ("id", "!=", s3.partner_id.commercial_partner_id.id), ("parent_id", "=", False)], limit=1)
API[s3.primavera_ecl_ref]["Entidade"] = outro.primavera_customer_code
a3 = foto(s3); m3 = mx()
c._resync_single_ecl(s3.primavera_ecl_ref); s3.invalidate_recordset(); b3 = foto(s3); n3 = novos(m3)
R("E3", s3.primavera_ecl_ref, ":", env["res.partner"].browse(a3["partner"]).name, "→", s3.partner_id.name, "| novos:", n3)
if PROPOSTA:
    check("E3 ECL activa sem faturas: cliente actualizado, resto igual (incl. tabela de preços e posição fiscal), sem notificações", b3["partner"] == outro.id and all(a3[k] == b3[k] for k in ("user", "team", "fpos", "pl", "pay", "docs", "lines", "seguidores", "state", "stage")) and n3["notificacoes"] == 0 and n3["emails"] == 0)

# E4 — troca simulada numa ECL com faturas: não muda
s4 = SO.search([("primavera_ecl_ref", "in", list(API)), ("primavera_fatura_refs", "!=", False)], limit=1)
if s4:
    outro4 = env["res.partner"].sudo().search([("primavera_customer_code", "!=", False), ("id", "!=", s4.partner_id.commercial_partner_id.id), ("parent_id", "=", False)], limit=1)
    API[s4.primavera_ecl_ref]["Entidade"] = outro4.primavera_customer_code
    a4 = foto(s4); c._resync_single_ecl(s4.primavera_ecl_ref); s4.invalidate_recordset()
    check("E4 ECL com faturas (" + s4.primavera_ecl_ref + "): o cliente não muda", s4.partner_id.id == a4["partner"])
else:
    R("E4 sem ECL com faturas nos dados")
R("TOTAL", sum(RES), "/", len(RES))
env.cr.rollback()
R("FIM")
