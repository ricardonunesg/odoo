# Fotografia (só leitura): linhas e totais de faturas e ECLs, documentos associados. Escreve SAIDA (json).
import json, hashlib
SAIDA = "__SAIDA__"
out = {"aml": {}, "sol": {}, "fat": {}, "ecl": {}, "docs": {}}
for l in env["account.move.line"].sudo().search([("move_id.primavera_ref", "!=", False)]):
    out["aml"][l.id] = [l.move_id.primavera_ref, l.product_id.default_code, l.quantity, l.price_unit, l.discount,
                        round(l.price_subtotal, 2), l.display_type, l.name, l.lote, l.peso_liquido, l.caixas, l.tax_ids.ids]
for l in env["sale.order.line"].sudo().search([("order_id.primavera_ecl_ref", "!=", False)]):
    out["sol"][l.id] = [l.order_id.primavera_ecl_ref, l.product_id.default_code, l.product_uom_qty, l.price_unit, l.discount,
                        round(l.price_subtotal, 2), l.display_type, l.name, l.lote, l.peso_liquido, l.caixas, l.tax_id.ids]
for m in env["account.move"].sudo().search([("primavera_ref", "!=", False)]):
    out["fat"][m.primavera_ref] = [m.id, m.state, round(m.amount_untaxed, 2), round(m.amount_tax, 2), m.partner_id.id, m.ecl_sale_order_id.id]
for s in env["sale.order"].sudo().with_context(active_test=False).search([("primavera_ecl_ref", "!=", False)]):
    out["ecl"][s.primavera_ecl_ref] = [s.id, s.state, s.stage_id.id, round(s.amount_untaxed, 2), round(s.amount_tax, 2), s.partner_id.id,
                                      len(s.ecl_doc_line_ids), s.primavera_fatura_refs]
for model in ["packing.list", "declaracao.lote", "certificado.salubridade", "certificado.qualidade", "boletim.analises"]:
    for r in env[model].sudo().search([]):
        lines = getattr(r, "line_ids", env[model])
        h = hashlib.md5(json.dumps([[str(v) for v in l.read([f for f in l._fields if f not in ("write_date", "write_uid", "__last_update")])[0].values()] for l in lines], sort_keys=True).encode()).hexdigest() if lines else ""
        out["docs"][f"{model}:{r.id}"] = [r.name, r.state, h]
json.dump(out, open(SAIDA, "w"), default=str)
print("R foto", SAIDA, {k: len(v) for k, v in out.items()})
