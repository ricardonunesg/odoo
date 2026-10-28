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

# T3 — Packing List a partir de uma fatura com artigo de 5 casas (TP.005.11.01000.02 = 11,4277 kg)
aml = env["account.move.line"].sudo().search([("product_id.default_code", "=", "TP.005.11.01000.02"), ("move_id.move_type", "=", "out_invoice")], limit=1)
mv = aml.move_id
R("T3 fatura", mv.name, "| peso unit. guardado:", aml.peso_bruto, "| total bruto fatura:", mv.total_peso_bruto)
aml.write({"peso_bruto": 11.4277})
mv.invalidate_recordset()
R("T3 depois de gravar 11,4277 na linha da fatura: guarda", aml.peso_bruto, "| total bruto fatura:", mv.total_peso_bruto)
pl = env["packing.list"].sudo().create({"fatura_id": mv.id, "template_id": env["packing.list.template"].sudo().search([], limit=1).id})
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
