# Importação com dados reais gravados da WebAPI (FA/2026/9 e FAT/2026/202), sem ligação ao Primavera.
import json
from unittest import mock
from odoo.addons.primavera_connector.models import primavera_connection as M
CODIGO = "__CODIGO__"
api = json.load(open("/out/p2_api.json"))
tot = json.load(open("/out/p2_tot.json"))
c = env["primavera.connection"].browse(1)
AM = env["account.move"].sudo()

def fake_edita(self, ep, strict=False):
    for ref in api:
        t, s, n = ref.split("/")
        if ep.endswith(f"/{t}/{s}/{n}"):
            return api[ref]
    if ep.endswith("/FA/2026/90009"):
        return api["FA/2026/9"]
    return None

with mock.patch.object(M.PrimaveraConnection, "_edita", fake_edita), \
     mock.patch.object(M.PrimaveraConnection, "_sql_connection", return_value=None):
    # (1) fatura nova (dados da FA/2026/9 com outro número)
    c._import_faturas_doc("FA", "2026", 90008, 1, 1, None)
    novo = AM.search([("primavera_ref", "=", "FA/2026/90009")])
    zeros = novo.invoice_line_ids.filtered(lambda l: l.product_id.default_code in ("PAL.1200.1000.01", "SERV.001"))
    print("R", CODIGO, "| FATURA NOVA (dados FA/2026/9): paletes/serviço preços", sorted(set(zeros.mapped("price_unit"))),
          "| total sem IVA Odoo", round(novo.amount_untaxed, 2), "| Primavera", tot["FA/2026/9"]["merc"])
    # (2) reimportação de uma fatura existente em rascunho (FAT/2026/202)
    antes = AM.search([("primavera_ref", "=", "FAT/2026/202")])
    tot_antes = round(antes.amount_untaxed, 2)
    c._import_faturas_doc("FAT", "2026", 201, 1, 1, None)
    depois = AM.search([("primavera_ref", "=", "FAT/2026/202")])
    pal = depois.invoice_line_ids.filtered(lambda l: (l.product_id.default_code or "").startswith("PAL"))
    print("R", CODIGO, "| REIMPORTAÇÃO FAT/2026/202: paletes", pal.mapped("price_unit"), "| total antes", tot_antes, "→ depois",
          round(depois.amount_untaxed, 2), "| Primavera (bruto)", tot["FAT/2026/202"]["merc"], "| com desconto?", tot["FAT/2026/202"]["tem_desconto"])
env.cr.rollback()
