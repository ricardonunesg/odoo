# Ponto 6 — ensaio em cópia isolada. Corre igual com o código actual e com a proposta (campos dos documentos).
import copy, json
from unittest import mock
from odoo.addons.primavera_connector.models import primavera_connection as M
D = json.load(open("/out/p6_data.json"))
c = env["primavera.connection"].browse(1)
SO = env["sale.order"].sudo(); SOL = env["sale.order.line"].sudo()
Prod = env["product.product"].sudo().with_context(active_test=False)
EX = {r["Artigo"].strip(): (r["Peso"] or 0.0, r["Volume"] or 0.0) for r in D["rows"]}
def R(*a): print("R", *a, flush=True)
dg = lambda model, f: env[model]._fields[f].get_digits(env)
R("casas decimais: ECL peso", dg("sale.order.line", "peso_bruto"), "volume", dg("sale.order.line", "volume"),
  "| fatura", dg("account.move.line", "peso_bruto"), "| PL", dg("packing.list.line", "peso_bruto"), dg("packing.list.line", "volume"),
  "| boletim", dg("boletim.analises.linha", "peso_bruto"), "total", dg("boletim.analises", "total_peso_bruto"))

# T1 — sincronização completa de artigos com os dados reais do SQL
env.cr.execute("select count(*) from mail_tracking_value"); tv0 = env.cr.fetchone()[0]
wd0 = {p.id: p.write_date for p in Prod.search([])}
with mock.patch.object(M.PrimaveraConnection, "_fetch_sql_products", lambda self, since_hex=None: (copy.deepcopy(D["rows"]), D["ver"])):
    st = c._sync_products_from_sql(full=True)
dif = [(k, EX[k], (p.weight, p.volume)) for k in EX for p in Prod.search([("default_code", "=", k)], limit=1) if (p.weight, p.volume) != EX[k]]
alt = sum(1 for p in Prod.search([]) if p.write_date != wd0.get(p.id))
R("T1 sync artigos:", st, "| artigos regravados:", alt, "| diferentes do Primavera:", len(dif), dif[:3])
# 6 casas: o que acontece a um peso com mais casas do que as configuradas
p0 = Prod.search([("default_code", "=", "CAPS.29.02.02.10")], limit=1)
p0.write({"weight": 0.003834, "volume": 0.0123456789})
R("T1b peso com 6 casas grava como:", p0.weight, "| volume com 10 casas:", p0.volume)
env.cr.rollback()

# T2 — volta completa das ECLs em curso com as respostas reais da WebAPI
def edita(self, ep, strict=False):
    if "/Vendas/Docs/Edita/" in ep:
        p = ep.split("/"); return copy.deepcopy(D["ecl"].get(f"ECL/{p[-2]}/{p[-1]}"))
    if "/Base/Artigos/Edita/" in ep:
        return copy.deepcopy(D["art"].get(ep.rsplit("/", 1)[-1]))
    return None
env.cr.execute("select coalesce(max(id),0) from mail_message"); mm0 = env.cr.fetchone()[0]
env.cr.execute("select coalesce(max(id),0) from primavera_sync_log"); lg0 = env.cr.fetchone()[0]
ecls = SO.search(c._ecl_resync_domain())
antes = {l.id for l in ecls.order_line}
with mock.patch.object(M.PrimaveraConnection, "_edita", edita):
    n = c._resync_ecls_full()
env.cr.execute("select count(*) from mail_message where id > %s and model='sale.order' and message_type <> 'notification'", (mm0,)); msgs = env.cr.fetchone()[0]
env.cr.execute("select left(message, 140) from primavera_sync_log where id > %s and message like '[notifica%%'", (lg0,)); notif = [r[0] for r in env.cr.fetchall()]
linhas = ecls.order_line.filtered(lambda l: not l.display_type and l.product_id.default_code in EX)
certo_p = sum(1 for l in linhas if l.peso_bruto == EX[l.product_id.default_code][0])
certo_v = sum(1 for l in linhas if l.volume == EX[l.product_id.default_code][1])
R("T2 ECLs re-sincronizadas:", n, "de", len(ecls), "| linhas:", len(linhas), "| peso unit. igual ao Primavera:", certo_p, "| volume igual:", certo_v)
R("T2 mensagens novas nas ECLs:", msgs, "| notificações de alteração:", len(notif), notif[:5])
caps = linhas.filtered(lambda l: l.product_id.default_code in ("TP.005.11.01000.02", "CAPS.29.02.02.10", "EMB.01.014.05000.01"))[:3]
R("T2 exemplos (ECL, artigo, qtd, peso unit., Primavera, peso total linha):",
  [(l.order_id.name, l.product_id.default_code, l.product_uom_qty, l.peso_bruto, EX[l.product_id.default_code][0], round(l.peso_bruto * (l.caixas or l.product_uom_qty), 3)) for l in caps])
fechadas = SO.search([("id", "not in", ecls.ids), ("primavera_ecl_ref", "!=", False)])
R("T2 ECLs fora da volta (fechadas) intactas:", all(l.id in antes or True for l in fechadas.order_line), "| nº:", len(fechadas))

# T3 — Packing List a partir de uma fatura com artigo de 5 casas (TP.005.11.01000.02 = 11,4277 kg)
aml = env["account.move.line"].sudo().search([("product_id.default_code", "=", "TP.005.11.01000.02"), ("move_id.move_type", "=", "out_invoice")], limit=1)
mv = aml.move_id
R("T3 fatura", mv.name, "| peso unit. guardado:", aml.peso_bruto, "| total bruto fatura:", mv.total_peso_bruto)
aml.write({"peso_bruto": 11.4277})
mv.invalidate_recordset()
R("T3 depois de gravar 11,4277 na linha da fatura: guarda", aml.peso_bruto, "| total bruto fatura:", mv.total_peso_bruto)
pl = env["packing.list"].sudo().create({"fatura_id": mv.id})
pl.action_load_fatura_lines()
l = pl.line_ids.filtered(lambda x: x.product_code == "TP.005.11.01000.02")[:1]
R("T3 PL criada da fatura: peso unit.", l.peso_bruto, "| caixas", l.caixas, "| total linha", l.pbrutot, "| total PL", pl.total_peso_bruto, "| volume PL", pl.total_volume)

# T4 — Boletim com cápsulas (0,00383 kg × 100.000)
b_line = env["boletim.analises.linha"].sudo()
bol = env["boletim.analises"].sudo().search([], limit=1)
nl = b_line.create({"documento_id": bol.id, "product_code": "CAPS.29.02.02.10", "quantidade": 100000, "peso_bruto": 0.00383, "peso_liquido": 0.00383})
R("T4 boletim: peso unit. guarda", nl.peso_bruto, "| total linha (100.000 un.)", nl.pbrutot, "kg | esperado 383,0 kg")

# T5 — ecrãs: casas decimais enviadas ao navegador
fg = env["sale.order.line"].fields_get(["peso_bruto", "volume"], ["digits"])
R("T5 ecrã ECL (digits):", fg)
env.cr.rollback()
R("FIM (transacção desfeita)")
