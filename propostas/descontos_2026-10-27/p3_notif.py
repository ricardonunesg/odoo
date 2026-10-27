# Notificações de alteração de ECL no re-sync (como o cron faz: só ECLs em curso), com dados reais gravados.
import copy, json
from unittest import mock
from odoo.addons.primavera_connector.models import primavera_connection as M
CENARIO = "__CENARIO__"
api = json.load(open("/out/p3_dados.json"))["api"]
c = env["primavera.connection"].browse(1)
SO = env["sale.order"].sudo()
avisos = []
def regista(self, so, body):
    avisos.append((so.primavera_ecl_ref, body))
def fake(dados):
    def f(self, ep, strict=False):
        return dados.get("/".join(ep.rstrip("/").split("/")[-3:]))
    return f
em_curso = SO.search(c._ecl_resync_domain() + [("primavera_ecl_ref", "in", [r for r in api if r.startswith("ECL/")])])
print("R ECLs com desconto em curso (re-sincronizáveis pelo cron):", len(em_curso))
with mock.patch.object(M.PrimaveraConnection, "_ecl_post_change", regista), \
     mock.patch.object(M.PrimaveraConnection, "_sql_connection", return_value=None):
    with mock.patch.object(M.PrimaveraConnection, "_edita", fake(api)):
        for so in em_curso:
            c._resync_single_ecl(so.primavera_ecl_ref)
    print("R", CENARIO, "| re-sync sem nada mudado no Primavera → avisos:", len(avisos),
          [(r, b.split("<li>")[1][:70]) for r, b in avisos[:3]])
    if CENARIO == "com_correcao":
        alvo = next(so.primavera_ecl_ref for so in em_curso if any(l.get("Artigo") and l.get("Desconto1") for l in api[so.primavera_ecl_ref]["Linhas"]))
        d2 = copy.deepcopy(api)
        l0 = next(l for l in d2[alvo]["Linhas"] if l.get("Artigo") and l.get("Desconto1"))
        l0["Desconto1"] = 5.0
        avisos.clear()
        with mock.patch.object(M.PrimaveraConnection, "_edita", fake(d2)):
            c._resync_single_ecl(alvo)
        print("R desconto alterado no Primavera (3% → 5%) em", alvo, "→ avisos:", len(avisos), [b.split("<ul>")[1][:160] for r, b in avisos])
        avisos.clear()
        with mock.patch.object(M.PrimaveraConnection, "_edita", fake(d2)):
            c._resync_single_ecl(alvo)
        print("R mesmo re-sync outra vez (nada mudou) → avisos:", len(avisos))
        l0["PrecUnit"] = round(float(l0["PrecUnit"]) + 0.10, 4)
        avisos.clear()
        with mock.patch.object(M.PrimaveraConnection, "_edita", fake(d2)):
            c._resync_single_ecl(alvo)
        print("R só o preço alterado → avisos:", len(avisos), [b.split("<ul>")[1][:160] for r, b in avisos])
env.cr.rollback()
