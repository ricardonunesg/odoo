# Peso líquido integrado — ensaio funcional numa cópia isolada já actualizada (-u) com a proposta.
import copy, json
from unittest import mock
from odoo.addons.primavera_connector.models import primavera_connection as M
D = json.load(open("/out/p6_data.json")); DC = json.load(open("/out/p6c_data.json")); DR = json.load(open("/out/p6d_rows.json"))
ART = dict(D["art"]); ART.update({k: v for k, v in DC["art"].items() if v})
EX = {r["Artigo"].strip(): r for r in DR["rows"]}
c = env["primavera.connection"].browse(1)
PT = env["product.template"].sudo().with_context(active_test=False)
SO = env["sale.order"].sudo(); AM = env["account.move"].sudo(); AML = env["account.move.line"].sudo()
RES = []
def R(*a): print("R", *a, flush=True)
def check(nome, cond, extra=""):
    RES.append(bool(cond)); R("PASS" if cond else "FAIL", "|", nome, ("| " + str(extra)) if extra else "")
def edita(self, ep, strict=False):
    p = ep.split("/")
    if "/Vendas/Docs/Edita/" in ep:
        k = f"{p[-3]}/{p[-2]}/{p[-1]}"; return copy.deepcopy(DC["fat"].get(k) or D["ecl"].get(k))
    if "/Base/Artigos/Edita/" in ep:
        return copy.deepcopy(ART.get(p[-1]))
    return None
for p in [mock.patch.object(M.PrimaveraConnection, "_edita", edita),
          mock.patch.object(M.PrimaveraConnection, "_sql_connection", lambda self: None),
          mock.patch.object(M.PrimaveraConnection, "_fetch_sql_products", lambda self, since_hex=None: (copy.deepcopy(DR["rows"]), DR["ver"]))]:
    p.start()

# F1 — sincronização dos artigos (volta completa) preenche o peso líquido
st = c._sync_products_from_sql(full=True)
R("F1 sync artigos:", st)
tm = {t.default_code: t for t in PT.search([("default_code", "!=", False)])}
dl = [(k, r["PesoLiquido"], tm[k].primavera_peso_liquido) for k, r in EX.items() if k in tm and (r["PesoLiquido"] or 0.0) != tm[k].primavera_peso_liquido]
db = [(k, r["Peso"], tm[k].weight) for k, r in EX.items() if k in tm and (r["Peso"] or 0.0) != tm[k].weight]
dv = [(k, r["Volume"], tm[k].volume) for k, r in EX.items() if k in tm and (r["Volume"] or 0.0) != tm[k].volume]
check("F1 peso líquido igual ao Primavera em todos os artigos (incl. 4–5 casas)", not dl, dl[:5])
check("F1 peso bruto e volume continuam iguais ao Primavera", not db and not dv, (db[:3], dv[:3]))
R("F1 exemplos (artigo, bruto, líquido, volume):", [(k, tm[k].weight, tm[k].primavera_peso_liquido, tm[k].volume) for k in ("OLIV.001.01.00350.01", "TP.001.10.00500.02", "CAPS.29.02.02.10", "EMB.01.014.05000.01", "ASA.36.01.10") if k in tm])
st2 = c._sync_products_from_sql(full=True)
check("F1 segunda volta: nenhum artigo regravado", st2.get("updated") == 0, st2)

# F2 — avisos na ficha do artigo
sem_b = PT.search([("primavera_aviso_pesos", "like", "Sem peso bruto%")])
sem_l = PT.search([("primavera_aviso_pesos", "like", "Sem peso líquido%")])
R("F2 avisos: sem peso bruto", len(sem_b), "| sem peso líquido", len(sem_l), sem_l.mapped("default_code"))
check("F2 os 132 artigos com líquido e sem bruto ficam assinalados (activos)", len(sem_b.filtered("active")) == 132, len(sem_b.filtered("active")))
check("F2 paletes não são assinaladas por falta de peso líquido", not sem_l.filtered(lambda t: (t.default_code or "").startswith("PAL")))
check("F2 filtro 'Pesos incompletos no Primavera' encontra-os", PT.search_count([("primavera_aviso_pesos", "!=", False)]) == len(sem_b) + len(sem_l))
arch = PT.get_views([(False, "form")])["views"]["form"]["arch"]
check("F2 ficha do artigo mostra Peso bruto, Peso Líquido e Volume + aviso", all(x in arch for x in ("primavera_peso_liquido", "Peso bruto", "primavera_aviso_pesos", 'name="volume"')))
fg = PT.fields_get(["weight", "primavera_peso_liquido", "volume"], ["digits", "string"])
R("F2 casas decimais na ficha:", {k: v.get("digits") for k, v in fg.items()})

# F3 — PL/2026/0001 recarregada da FA/2026/171 tal como está (linhas sem peso líquido → ficha do artigo)
pl = env["packing.list"].sudo().browse(36)
antes = pl.total_peso_liquido
m0 = pl.message_ids.ids
pl.action_load_fatura_lines()
R("F3 PL/2026/0001 por artigo (artigo | caixas | bruto/cx | líquido/cx | bruto linha | líquido linha):")
for l in pl.line_ids.sorted("sequence"):
    R(f"   {l.product_code} | {l.caixas} | {l.peso_bruto} | {l.peso_liquido} | {l.pbrutot} | {l.pliquidot}{' | palete' if l.is_palete else ''}")
R("F3 TOTAIS: líquido", pl.total_peso_liquido, "| bruto", pl.total_peso_bruto, "| volume", pl.total_volume, "| caixas", pl.total_caixas)
check("F3 PL/2026/0001: total líquido 14.282,748 kg (antes 16.733,628)", round(pl.total_peso_liquido, 3) == 14282.748, (antes, pl.total_peso_liquido))
check("F3 OLIV: 6,96 kg líquido/cx e 10,68 bruto/cx", all(l.peso_liquido == 6.96 and l.peso_bruto == 10.68 for l in pl.line_ids if l.product_code.startswith("OLIV")))
check("F3 contas por linha: líquido linha = caixas × líquido/cx; bruto idem", all(abs(l.pliquidot - (0 if l.is_palete else l.caixas * l.peso_liquido)) < 0.0005 and abs(l.pbrutot - l.caixas * l.peso_bruto) < 0.0005 for l in pl.line_ids))
check("F3 sem aviso (todos os artigos da FA/2026/171 têm os dois pesos)", pl.message_ids.ids == m0)

# F4 — FA/2026/171 reimportada (rascunho): linha do Primavera → ficha do artigo
c._import_faturas_doc("FA", "2026", 170, 1, 1, None)
fa = AM.search([("name", "=", "FA/2026/171")], limit=1)
ol = fa.invoice_line_ids.filtered(lambda l: (l.product_id.default_code or "").startswith(("OLIV", "TP.001.10.00500")))
check("F4 FA/2026/171: linhas sem peso líquido no Primavera ficam com o da ficha (6,96 / 6,87)", sorted(ol.mapped("peso_liquido")) == [6.87, 6.96, 6.96], ol.mapped("peso_liquido"))
check("F4 linhas com peso líquido no Primavera mantêm o da linha", all(l.peso_liquido == next((x.get("IntrastatMassaLiq") for x in DC["fat"]["FA/2026/171"]["Linhas"] if x.get("Artigo") == l.product_id.default_code), l.peso_liquido) or l.product_id.default_code.startswith(("OLIV", "TP.001.10.00500")) for l in fa.invoice_line_ids.filtered("product_id")))
R("F4 totais FA/2026/171: líquido", fa.total_peso_liquido, "| bruto", fa.total_peso_bruto)
check("F4 total líquido da fatura = total líquido da PL", round(fa.total_peso_liquido, 3) == round(pl.total_peso_liquido, 3), (fa.total_peso_liquido, pl.total_peso_liquido))

# F5 — FAT/2026/47 (vendas à unidade, embalagens sem peso bruto no Primavera)
c._import_faturas_doc("FAT", "2026", 46, 1, 1, None)
ft = AM.search([("name", "=", "FAT/2026/47")], limit=1)
for l in ft.invoice_line_ids.filtered(lambda x: x.product_id.default_code):
    R(f"F5 {l.product_id.default_code} | {l.quantity} un | bruto/un {l.peso_bruto} | líquido/un {l.peso_liquido} | bruto linha {round(l.quantity * l.peso_bruto, 3)} | líquido linha {round(l.quantity * l.peso_liquido, 3)}")
R("F5 totais FAT/2026/47: líquido", ft.total_peso_liquido, "| bruto", ft.total_peso_bruto)
tpl = env["packing.list.template"].sudo().search([], limit=1)
pl2 = env["packing.list"].sudo().create({"fatura_id": ft.id, "template_id": tpl.id})
pl2.action_load_fatura_lines()
msg = pl2.message_ids.filtered(lambda m: "pesos em falta" in (m.body or ""))
R("F5 aviso na PL da FAT/2026/47:", msg[:1].body if msg else None)
check("F5 aviso lista as embalagens sem peso bruto e o artigo sem nenhum peso", msg and all(x in msg[0].body for x in ("EMB.01.021.10000.40", "EMB.01.002.01000.01", "CAPS.48.01.05.10")))
check("F5 cápsulas: 0,00354 kg líquido/un e 0,00383 bruto/un", all(l.peso_liquido == 0.00354 and l.peso_bruto == 0.00383 for l in pl2.line_ids if l.product_code.startswith("CAPS.29")))

# F6 — certificados e boletim a partir da FA/2026/171
for model in ("certificado.qualidade", "certificado.salubridade"):
    cert = env[model].sudo().search([], limit=1)
    if cert:
        cert.write({"fatura_id": fa.id}); cert.action_carregar_linhas_fatura()
        R("F6", model, [(x.display_name, x.peso_liquido_total) for x in env[model].sudo().search([("fatura_id", "=", fa.id)])])
bol = env["boletim.analises"].sudo().search([], limit=1)
bol.write({"fatura_id": fa.id, "state": "draft"}); bol.action_load_fatura_lines()
R("F6 boletins:", [(d.name, d.total_peso_liquido, d.total_peso_bruto) for d in env["boletim.analises"].sudo().search([("fatura_id", "=", fa.id)])])

# F7 — ECLs em curso (volta completa)
env.cr.execute("select coalesce(max(id),0) from primavera_sync_log"); lg0 = env.cr.fetchone()[0]
env.cr.execute("select coalesce(max(id),0) from mail_message"); mm0 = env.cr.fetchone()[0]
ecls = SO.search(c._ecl_resync_domain()); n = c._resync_ecls_full()
ls = ecls.filtered(lambda s: s.state != "cancel").order_line.filtered(lambda l: not l.display_type and l.product_id.default_code and not l.product_id.default_code.startswith("PAL"))
sem = ls.filtered(lambda l: not l.peso_liquido and l.product_id.primavera_peso_liquido)
da_ficha = ls.filtered(lambda l: l.peso_liquido and l.peso_liquido == l.product_id.primavera_peso_liquido)
env.cr.execute("select count(*) from primavera_sync_log where id > %s and message like '[notifica%%'", (lg0,)); notif = env.cr.fetchone()[0]
env.cr.execute("select count(*) from mail_message where id > %s and model='sale.order' and message_type <> 'notification'", (mm0,)); msgs = env.cr.fetchone()[0]
R("F7 ECLs:", n, "| linhas activas", len(ls), "| líquido igual à ficha", len(da_ficha), "| sem líquido com ficha preenchida", len(sem))
check("F7 nenhuma linha activa fica sem peso líquido quando a ficha o tem", not sem, [(l.order_id.name, l.product_id.default_code) for l in sem][:5])
check("F7 sem notificações nem mensagens nas ECLs", notif == 0 and msgs == 0, (notif, msgs))
R("TOTAL", sum(RES), "/", len(RES))
env.cr.rollback()
R("FIM")
