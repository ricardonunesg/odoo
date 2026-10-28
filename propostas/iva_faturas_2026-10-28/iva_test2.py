# Verificação diária com IVA/total + correcção das 24 — ensaio em cópia isolada.
import copy, json
from unittest import mock
from odoo.addons.primavera_connector.models import primavera_connection as M
D = json.load(open("/out/iva_data.json"))
c = env["primavera.connection"].browse(1)
AM = env["account.move"].sudo()
RES = []
def R(*a): print("R", *a, flush=True)
def check(nome, cond, extra=""):
    RES.append(bool(cond)); R("PASS" if cond else "FAIL", "|", nome, ("| " + str(extra)) if extra else "")
def edita(self, ep, strict=False):
    p = ep.split("/")
    if "/Vendas/Docs/Edita/" in ep:
        return copy.deepcopy(D["api"].get(f"{p[-3]}/{p[-2]}/{p[-1]}"))
    if "/Base/Artigos/Edita/" in ep:
        return copy.deepcopy(D["art"].get(p[-1]))
    return None
class Cur:
    def __init__(s): s.rows = []
    def __enter__(s): return s
    def __exit__(s, *a): return False
    def execute(s, q, params=None):
        if "FROM CabecDoc" in q:
            s.rows = [(k.split("/")[0], k.split("/")[1], int(k.split("/")[2]), (D["api"].get(k) or {}).get("Nome", ""), h["iva"], h["total"], h["anulado"]) for k, h in D["H"].items()]
        else:
            s.rows = []
    def fetchall(s): return s.rows
class Conn:
    def cursor(s): return Cur()
    def close(s): pass
for p in [mock.patch.object(M.PrimaveraConnection, "_edita", edita),
          mock.patch.object(M.PrimaveraConnection, "_sql_connection", lambda self: Conn())]:
    p.start()
AFECTADAS = ["FA/2026/170", "FA/2026/172", "FA/2026/174", "FA/2026/175", "FA/2026/176", "FA/2026/180", "FA/2026/181", "FA/2026/183", "FA/2026/184",
             "FA/2026/185", "FA/2026/186", "FA/2026/187", "FA/2026/189", "FA/2026/193", "FA/2026/197", "FA/2026/198", "FA/2026/200",
             "FAT/2026/192", "FAT/2026/194", "FAT/2026/195", "FAT/2026/201", "FAT/2026/202", "FAT/2026/205", "FAT/2026/206"]
def fotos():
    return {m.primavera_ref: (round(m.amount_untaxed, 2), round(m.amount_tax, 2), round(m.amount_total, 2), m.state, tuple(m.invoice_line_ids.ids)) for m in AM.search([("primavera_ref", "=like", "F%/2026/%")])}
def ultimo_log():
    return env["primavera.sync.log"].sudo().search([("operation", "=", "faturas")], order="id desc", limit=1).message
env.cr.execute("select coalesce(max(id),0) from mail_message"); mm0 = env.cr.fetchone()[0]
f0 = fotos()

# V1 — verificação com as faturas tal como estão (25 diferentes > limite 20 → só avisa, não mexe)
c._verify_faturas()
R("V1 log:", ultimo_log()[:400])
f1 = fotos()
check("V1 com 25 diferenças (> 20) não reimporta nada, só avisa", f1 == f0 and "demasiadas" in ultimo_log())

# V2 — correcção pontual das 24 (reimportação, uma a uma)
for ref in AFECTADAS:
    t, s, n = ref.split("/"); c._import_faturas_doc(t, s, int(n) - 1, 1, 1, None)
f2 = fotos()
mud = [k for k in f0 if f0[k][:4] != f2[k][:4]]
check("V2 só as 24 faturas mudam de valores", sorted(mud) == sorted(AFECTADAS), sorted(set(mud) ^ set(AFECTADAS)))
ok24 = [r for r in AFECTADAS if abs(f2[r][1] - D["H"][r]["iva"]) <= 0.05 and abs(f2[r][2] - D["H"][r]["total"]) <= 0.05]
check("V2 as 24 ficam com IVA e total iguais ao Primavera", len(ok24) == 24, sorted(set(AFECTADAS) - set(ok24)))
check("V2 continuam em rascunho", all(f2[r][3] == "draft" for r in AFECTADAS))
R("V2 exemplos (ref: IVA antes → depois | Primavera):", [(r, f0[r][1], f2[r][1], D["H"][r]["iva"]) for r in ("FA/2026/176", "FA/2026/172", "FAT/2026/194", "FA/2026/198")])

# V3 — verificação depois da correcção: só a FAT/2026/185 (diferença de base já conhecida) fica a ver
c._verify_faturas()
R("V3 log:", ultimo_log()[:400])
f3 = fotos()
check("V3 só a FAT/2026/185 aparece (reimportada 1 vez, continua diferente → aviso)", "FAT/2026/185" in ultimo_log() and "1 a precisar" in ultimo_log())
check("V3 nenhuma outra fatura mexida", all(f3[k] == f2[k] for k in f2 if k != "FAT/2026/185"))

# V4 — terceira verificação: não volta a reimportar a FAT/2026/185 nem a notificar
env.cr.execute("select coalesce(max(id),0) from mail_message"); mm3 = env.cr.fetchone()[0]
c._verify_faturas()
f4 = fotos()
env.cr.execute("select count(*) from mail_message where id > %s", (mm3,)); n4 = env.cr.fetchone()[0]
check("V4 FAT/2026/185 não é reimportada outra vez (linhas iguais) e não há nova notificação", f4["FAT/2026/185"] == f3["FAT/2026/185"] and n4 == 0, n4)

# V5 — erro futuro numa fatura em rascunho: taxa trocada → a verificação corrige sozinha
com_iva = AM.search([("primavera_ref", "=like", "FA/2026/%"), ("state", "=", "draft"), ("amount_tax", ">", 0), ("primavera_ref", "not in", AFECTADAS)], order="id desc", limit=2)
REF5, REF6 = com_iva[0].primavera_ref, com_iva[1].primavera_ref
R("V5/V6 faturas usadas:", REF5, REF6)
fx = AM.search([("primavera_ref", "=", REF5)])
l6 = fx.invoice_line_ids.filtered(lambda l: l.tax_ids)[:1]
t23 = env["account.tax"].sudo().search([("type_tax_use", "=", "sale"), ("amount", "=", 23), ("name", "=", "23%")], limit=1)
t6 = env["account.tax"].sudo().search([("type_tax_use", "=", "sale"), ("amount", "=", 6), ("name", "=", "6%")], limit=1)
outra = t6 if l6.tax_ids == t23 else t23
l6.tax_ids = [(6, 0, outra.ids)]
R("V5 estragada: IVA", fx.amount_tax, "| Primavera", D["H"][REF5]["iva"])
c._verify_faturas()
fx = AM.search([("primavera_ref", "=", REF5)])
R("V5 log:", ultimo_log()[:300])
check("V5 rascunho com IVA errado é reimportado e fica igual ao Primavera", abs(fx.amount_tax - D["H"][REF5]["iva"]) <= 0.05 and "1 corrigida(s)" in ultimo_log(), (fx.amount_tax, D["H"][REF5]["iva"]))

# V6 — fatura lançada com diferença: não é alterada, só avisa
fy = AM.search([("primavera_ref", "=", REF6)])
ly = fy.invoice_line_ids.filtered(lambda l: l.tax_ids)[:1]
ly.tax_ids = [(6, 0, (t6 if ly.tax_ids == t23 else t23).ids)]
iva_y = fy.amount_tax
env.cr.execute("update account_move set state='posted' where id=%s", (fy.id,)); fy.invalidate_recordset()
c._verify_faturas()
fy = AM.search([("primavera_ref", "=", REF6)])
R("V6 log:", ultimo_log()[:300])
check("V6 fatura lançada não é alterada e fica em aviso", abs(fy.amount_tax - iva_y) < 0.001 and f"{REF6} — " in ultimo_log() and "lançada" in ultimo_log().split(f"{REF6} — ")[1][:250])
env.cr.execute("select count(*) from mail_message where id > %s and message_type='user_notification'", (mm0,)); R("notificações enviadas no ensaio:", env.cr.fetchone()[0])
R("TOTAL", sum(RES), "/", len(RES))
env.cr.rollback()
R("FIM")
