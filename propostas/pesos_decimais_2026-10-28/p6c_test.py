# Alteração C (peso líquido) — ensaio em cópia isolada. Corre igual com o código de produção e com a proposta.
import copy, json
from unittest import mock
from odoo.addons.primavera_connector.models import primavera_connection as M
D = json.load(open("/out/p6_data.json")); DC = json.load(open("/out/p6c_data.json"))
ART = dict(D["art"]); ART.update({k: v for k, v in DC["art"].items() if v})
c = env["primavera.connection"].browse(1)
SO = env["sale.order"].sudo(); AM = env["account.move"].sudo()
PROPOSTA = hasattr(M.PrimaveraConnection, "_primavera_pesos_liquidos")
def R(*a): print("R", *a, flush=True)
R("versão:", "PROPOSTA C" if PROPOSTA else "produção actual")
API_OK = [True]
def edita(self, ep, strict=False):
    if not API_OK[0]:
        return None
    p = ep.split("/")
    if "/Vendas/Docs/Edita/" in ep:
        k = f"{p[-3]}/{p[-2]}/{p[-1]}"
        return copy.deepcopy(DC["fat"].get(k) or D["ecl"].get(k))
    if "/Base/Artigos/Edita/" in ep:
        return copy.deepcopy(ART.get(p[-1]))
    return None
patches = [mock.patch.object(M.PrimaveraConnection, "_edita", edita),
           mock.patch.object(M.PrimaveraConnection, "_sql_connection", lambda self: None)]
for p in patches: p.start()

def mostra_pl(pl, tit):
    for l in pl.line_ids.filtered(lambda x: x.product_code.startswith(("OLIV", "TP.001.10.00500"))):
        R(f"   {tit}: {l.product_code} | caixas {l.caixas} | líquido/cx {l.peso_liquido} | bruto/cx {l.peso_bruto} | líquido linha {l.pliquidot} | bruto linha {l.pbrutot}")
    R(f"   {tit}: TOTAL PL líquido {pl.total_peso_liquido} kg | bruto {pl.total_peso_bruto} kg | volume {pl.total_volume} m³ | caixas {pl.total_caixas}")

# C1 — PL/2026/0001 (id 36) recarregada da FA/2026/171 tal como está (linhas sem peso líquido)
fa = AM.search([("name", "=", "FA/2026/171")], limit=1)
pl = env["packing.list"].sudo().browse(36)
R("C1 PL", pl.name, pl.state, "| fatura", pl.fatura_id.name, "| ANTES: líquido", pl.total_peso_liquido, "bruto", pl.total_peso_bruto)
pl.action_load_fatura_lines()
mostra_pl(pl, "C1 depois de recarregar")

# C2 — Primavera indisponível: comportamento de recurso
API_OK[0] = False
pl.action_load_fatura_lines()
R("C2 Primavera indisponível → líquido OLIV/cx:", pl.line_ids.filtered(lambda x: x.product_code == "OLIV.001.01.00350.01").peso_liquido, "| total líquido", pl.total_peso_liquido)
API_OK[0] = True

# C3 — FA/2026/171 reimportada (rascunho → reescrita) e PL recarregada
st = c._import_faturas_doc("FA", "2026", 170, 1, 1, None)
fa = AM.search([("name", "=", "FA/2026/171")], limit=1)
R("C3 reimportação FA/2026/171:", st, "| estado", fa.state)
for l in fa.invoice_line_ids.filtered(lambda x: x.display_type == "product" and x.product_id.default_code):
    a = ART.get(l.product_id.default_code) or {}
    R(f"   {l.product_id.default_code} | qtd {l.quantity} | caixas {l.caixas} | líquido/cx {l.peso_liquido} (Primavera artigo {a.get('PesoLiquido')}) | bruto/cx {l.peso_bruto} (artigo {a.get('Peso')}) | líquido linha {round((l.caixas or l.quantity) * l.peso_liquido, 3)}")
R("C3 TOTAIS FA/2026/171: líquido", fa.total_peso_liquido, "| bruto", fa.total_peso_bruto, "| volume", fa.total_volume)
pl.action_load_fatura_lines()
mostra_pl(pl, "C3 PL recarregada")

# C4 — FAT/2026/47: cápsulas vendidas à unidade
st = c._import_faturas_doc("FAT", "2026", 46, 1, 1, None)
ft = AM.search([("name", "=", "FAT/2026/47")], limit=1)
for l in ft.invoice_line_ids.filtered(lambda x: x.display_type == "product" and (x.product_id.default_code or "").startswith(("CAPS.29", "EMB.01.014"))):
    R(f"C4 {l.product_id.default_code} | {l.quantity} UN | líquido/un {l.peso_liquido} | bruto/un {l.peso_bruto} | líquido linha {round(l.quantity * l.peso_liquido, 3)} kg | bruto linha {round(l.quantity * l.peso_bruto, 3)} kg")
R("C4 TOTAIS FAT/2026/47: líquido", ft.total_peso_liquido, "| bruto", ft.total_peso_bruto)

# C5 — ECLs em curso: volta completa
env.cr.execute("select coalesce(max(id),0) from primavera_sync_log"); lg0 = env.cr.fetchone()[0]
env.cr.execute("select coalesce(max(id),0) from mail_message"); mm0 = env.cr.fetchone()[0]
ecls = SO.search(c._ecl_resync_domain())
n = c._resync_ecls_full()
linhas = ecls.order_line.filtered(lambda l: not l.display_type and l.product_id.default_code and not l.product_id.default_code.startswith("PAL"))
sem = [l for l in linhas if not l.peso_liquido and (ART.get(l.product_id.default_code) or {}).get("PesoLiquido")]
igual_bruto = [l for l in linhas if l.peso_liquido and l.peso_liquido == l.peso_bruto and (ART.get(l.product_id.default_code) or {}).get("PesoLiquido") not in (None, 0, l.peso_bruto)]
env.cr.execute("select count(*) from primavera_sync_log where id > %s and message like '[notifica%%'", (lg0,)); notif = env.cr.fetchone()[0]
env.cr.execute("select count(*) from mail_message where id > %s and model='sale.order' and message_type <> 'notification'", (mm0,)); msgs = env.cr.fetchone()[0]
R("C5 ECLs re-sincronizadas", n, "| linhas", len(linhas), "| sem peso líquido mas o artigo tem:", len(sem), [(l.order_id.name, l.product_id.default_code) for l in sem][:6],
  "| líquido = bruto indevido:", len(igual_bruto), "| notificações", notif, "| mensagens", msgs)

# C6 — boletim e certificado a partir da FA/2026/171 (já reimportada)
bol = env["boletim.analises"].sudo().search([], limit=1)
if bol:
    bol.write({"fatura_id": fa.id, "state": "draft"})
    try:
        bol.action_load_fatura_lines()
        docs = env["boletim.analises"].sudo().search([("fatura_id", "=", fa.id)])
        R("C6 boletins da FA/2026/171:", [(d.name, d.total_peso_liquido, d.total_peso_bruto) for d in docs])
        lo = docs.line_ids.filtered(lambda x: x.product_code.startswith("OLIV"))
        R("C6 linhas OLIV no boletim:", [(x.product_code, x.quantidade, x.peso_liquido, x.pliquidot) for x in lo])
    except Exception as e:
        R("C6 boletim: erro", str(e)[:200])
for model in ("certificado.qualidade", "certificado.salubridade"):
    cert = env[model].sudo().search([], limit=1)
    if not cert:
        R("C6", model, "sem registos para testar"); continue
    try:
        cert.write({"fatura_id": fa.id})
        cert.action_carregar_linhas_fatura()
        certs = env[model].sudo().search([("fatura_id", "=", fa.id)])
        R("C6", model, "peso líquido total:", [(x.display_name, x.peso_liquido_total) for x in certs])
    except Exception as e:
        R("C6", model, "erro", str(e)[:200])
for p in patches: p.stop()
env.cr.rollback()
R("FIM (transacção desfeita)")
