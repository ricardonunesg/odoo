MODO = "__MODO__"   # A = código + dados corrigidos ; B = só código (contadores como hoje)
RES = []
def check(nome, cond, extra=""):
    RES.append(bool(cond))
    print("R", "PASS" if cond else "FAIL", "|", nome, ("| " + str(extra)) if extra else "")

Seq = env["ir.sequence"].sudo()
assert hasattr(Seq, "next_by_code_sem_repetir"), "código novo não carregado"
MODELOS = ["packing.list", "declaracao.lote", "certificado.salubridade", "certificado.qualidade",
           "boletim.analises", "certificado.conformidade.alimentar"]
antes = {m: {r.id: r.name for r in env[m].sudo().with_context(active_test=False).search([])} for m in MODELOS}

def prox(sid):
    return Seq.browse(sid).number_next_actual

if MODO == "A":
    check("contadores após dados: PL 5, DL 2, CS 3, BA 5", (prox(37), prox(38), prox(39), prox(41)) == (5, 2, 3, 5),
          (prox(37), prox(38), prox(39), prox(41)))
    check("QC (42) arquivada e CQ (40) activa", not Seq.browse(42).active and Seq.browse(40).active)
else:
    check("contadores como hoje: PL 1, DL 1, CS 1, BA 2", (prox(37), prox(38), prox(39), prox(41)) == (1, 1, 1, 2))

def novo(model):
    M = env[model].sudo()
    r = M.search([("name", "=", "Novo")], limit=1)
    if not r:
        r = M.search([], limit=1).copy()
    return r

def confirmar(model):
    r = novo(model)
    r.action_confirm()
    return r.name

pl1 = confirmar("packing.list")
check("Packing List nova", pl1 == "PL/2026/0005", pl1)
dl1 = confirmar("declaracao.lote")
check("Declaração de Lote nova", dl1 == "DL/2026/0002", dl1)
cs1 = confirmar("certificado.salubridade")
check("Certificado de Salubridade novo", cs1 == "CS/2026/0003", cs1)
cq1 = confirmar("certificado.qualidade")
check("Certificado de Qualidade novo (prefixo CQ)", cq1 == "CQ/2026/0001", cq1)
ba1 = confirmar("boletim.analises")
check("Boletim de Análises novo", ba1 == "BA/2026/0005", ba1)
cca = Seq.next_by_code_sem_repetir("certificado.conformidade.alimentar", "certificado.conformidade.alimentar")
check("Conformidade Alimentar (primeiro)", cca == "CCA/2026/0001", cca)

# contador reposto a 1 (o que uma actualização antiga fazia) → não pode repetir
env.cr.execute("SELECT setval('ir_sequence_037', 1, false), setval('ir_sequence_041', 1, false)")
pl2 = confirmar("packing.list")
check("contador PL reposto a 1 → salta os usados", pl2 == "PL/2026/0006", pl2)
ba2 = confirmar("boletim.analises")
check("contador BA reposto a 1 → salta os usados", ba2 == "BA/2026/0006", ba2)

# caminho "Imprimir PDF" também atribui número
r = novo("packing.list")
r.action_print_pdf()
check("Imprimir PDF atribui número livre", r.name == "PL/2026/0007", r.name)

# documentos existentes intactos e sem repetidos novos
depois = {m: {r.id: r.name for r in env[m].sudo().with_context(active_test=False).search([])} for m in MODELOS}
mudados = [(m, i, antes[m][i], depois[m].get(i)) for m in MODELOS for i in antes[m]
           if depois[m].get(i) != antes[m][i] and antes[m][i] != "Novo"]
check("nenhum documento já numerado mudou de número", not mudados, mudados[:5])
apagados = [(m, i) for m in MODELOS for i in antes[m] if i not in depois[m]]
check("nenhum documento apagado", not apagados, apagados[:5])
novos_nums = [n for n in (pl1, dl1, cs1, cq1, ba1, pl2, ba2, r.name)]
usados_antes = {n for m in MODELOS for n in antes[m].values()}
check("números novos não existiam antes e não se repetem entre si",
      not (set(novos_nums) & usados_antes) and len(set(novos_nums)) == len(novos_nums), novos_nums)
print("R TOTAL", sum(RES), "/", len(RES))
env.cr.rollback()
