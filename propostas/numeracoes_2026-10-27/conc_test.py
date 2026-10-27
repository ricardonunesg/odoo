import threading
from collections import Counter
from odoo import api, SUPERUSER_ID

RES = []
def check(nome, cond, extra=""):
    RES.append(bool(cond))
    print("R", "PASS" if cond else "FAIL", "|", nome, ("| " + str(extra)) if extra else "", flush=True)

reg = env.registry
Seq = env["ir.sequence"].sudo()
assert hasattr(Seq, "next_by_code_sem_repetir"), "código novo não carregado"
SEQ = {"packing.list": 37, "boletim.analises": 41, "certificado.salubridade": 39}
N = 25          # utilizadores em simultâneo
RONDAS = 6

def criar_rascunhos(model, n):
    M = env[model].sudo()
    base = M.search([("name", "!=", "Novo")], order="id", limit=1)
    # campos de escolha com valores antigos que já não existem na lista (ex.: modo_transporte 'Outro')
    defaults = {}
    for fname, f in base._fields.items():
        if f.type == "selection" and f.store and base[fname] and \
                base[fname] not in [k for k, _v in f._description_selection(env)]:
            defaults[fname] = False
    ids = [base.copy(defaults).id for _ in range(n)]
    env.cr.commit()
    return ids

def emitir_em_simultaneo(model, ids, metodo_por_id):
    barreira = threading.Barrier(len(ids), timeout=120)
    out = []
    def trabalhador(rid, metodo):
        with reg.cursor() as cr:
            e = api.Environment(cr, SUPERUSER_ID, {})
            rec = e[model].browse(rid)
            rec.name  # carrega antes da partida
            barreira.wait()
            try:
                getattr(rec, metodo)()
                cr.commit()
                out.append(("ok", rid, rec.name))
            except Exception as ex:
                cr.rollback()
                out.append(("erro", rid, type(ex).__name__))
    th = [threading.Thread(target=trabalhador, args=(rid, metodo_por_id(i))) for i, rid in enumerate(ids)]
    for t in th: t.start()
    for t in th: t.join()
    return out

def todos_os_nomes(model):
    env.invalidate_all()
    return [r.name for r in env[model].sudo().with_context(active_test=False).search([]) if r.name != "Novo"]

for model in SEQ:
    antes = Counter(todos_os_nomes(model))
    dups_antes = {k for k, v in antes.items() if v > 1}
    emitidos, erros = [], []
    for ronda in range(RONDAS):
        if ronda % 2 == 1:   # rondas ímpares: contador reposto a 1 (muitos números a saltar, em simultâneo)
            env.cr.execute(f"SELECT setval('ir_sequence_{SEQ[model]:03d}', 1, false)")
            env.cr.commit()
        ids = criar_rascunhos(model, N)
        metodo = (lambda i: "action_confirm") if ronda < 4 else (lambda i: "action_confirm" if i % 2 else "action_print_pdf")
        out = emitir_em_simultaneo(model, ids, metodo)
        emitidos += [o[2] for o in out if o[0] == "ok"]
        erros += [o for o in out if o[0] != "ok"]
    depois = Counter(todos_os_nomes(model))
    novos_dups = {k: v for k, v in depois.items() if v > 1 and k not in dups_antes}
    colidem = [n for n in emitidos if n in antes]
    check(f"{model}: {len(emitidos)} emitidos por {N} utilizadores em simultâneo ({RONDAS} rondas, 3 com contador reposto a 1)",
          len(emitidos) == N * RONDAS and not erros, f"erros={erros[:3]}")
    check(f"{model}: nenhum número repetido entre os emitidos", len(set(emitidos)) == len(emitidos),
          [k for k, v in Counter(emitidos).items() if v > 1][:5])
    check(f"{model}: nenhum emitido igual a um já existente (incl. cancelados e rascunhos)", not colidem, colidem[:5])
    check(f"{model}: nenhum repetido novo na base de dados", not novos_dups, novos_dups)
    print("R    ex.:", sorted(emitidos)[:3], "…", sorted(emitidos)[-2:], flush=True)

# Duas pessoas a confirmar o MESMO documento no mesmo instante
model = "packing.list"
rid = criar_rascunhos(model, 1)[0]
out = emitir_em_simultaneo(model, [rid, rid], lambda i: "action_confirm")
env.invalidate_all()
doc = env[model].browse(rid)
nome = doc.name
check("mesmo documento confirmado por 2 utilizadores ao mesmo tempo: fica com 1 número, sem repetidos",
      nome != "Novo" and Counter(todos_os_nomes(model))[nome] == 1, (nome, [o[0] + ":" + str(o[2]) for o in out]))

# Ano: um número de 2027 não bloqueia o de 2026, e vice-versa
M = env[model].sudo()
env.cr.execute("SELECT last_value FROM ir_sequence_037")
prox = env.cr.fetchone()[0] + 1
d2027 = M.browse(criar_rascunhos(model, 1)[0]); d2027.name = f"PL/2027/{prox:04d}"; env.cr.commit()
n2026 = Seq.with_context(ir_sequence_date="2026-12-31").next_by_code_sem_repetir("packing.list", "packing.list")
check("ano: PL/2027/N existente não bloqueia PL/2026/N", n2026 == f"PL/2026/{prox:04d}", (n2026, d2027.name))
env.cr.execute(f"SELECT setval('ir_sequence_037', {prox - 1}, {'true' if prox > 1 else 'false'})")
n2027 = Seq.with_context(ir_sequence_date="2027-01-05").next_by_code_sem_repetir("packing.list", "packing.list")
check("ano: em 2027 o mesmo número já usado em 2027 é saltado", n2027 == f"PL/2027/{prox + 1:04d}", n2027)

# Tipo: números de outro tipo de documento não interferem (o CS/2026/N existe; PL/2026/N não)
env.cr.execute("SELECT last_value FROM ir_sequence_039")
cs_ult = env.cr.fetchone()[0]
env.cr.execute(f"SELECT setval('ir_sequence_037', {cs_ult - 1}, true)")
npl = Seq.next_by_code_sem_repetir("packing.list", "packing.list")
check("tipo: só compara com documentos do mesmo tipo", npl.startswith("PL/2026/") and int(npl[-4:]) >= cs_ult, npl)

# Cancelados: número só existente num documento cancelado não volta a ser dado
env.cr.execute("SELECT last_value FROM ir_sequence_037")
alvo = env.cr.fetchone()[0] + 1
canc = M.browse(criar_rascunhos(model, 1)[0])
canc.write({"name": f"PL/2026/{alvo:04d}", "state": "cancelled"}); env.cr.commit()
n = Seq.next_by_code_sem_repetir("packing.list", "packing.list")
check("cancelados: número de um documento cancelado é saltado", n == f"PL/2026/{alvo + 1:04d}", (canc.name, n))
env.cr.rollback()
print("R TOTAL", sum(RES), "/", len(RES), flush=True)
