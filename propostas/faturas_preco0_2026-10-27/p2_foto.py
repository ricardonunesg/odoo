# Fotografia (só leitura) das faturas e documentos para comparar antes/depois. Escreve /tmp/<nome>.json
import json, hashlib
NOME = "__NOME__"
out = {"linhas": {}, "faturas": {}, "docs": {}}
for l in env["account.move.line"].sudo().search([("move_id.primavera_ref", "!=", False)]):
    out["linhas"][l.id] = [l.move_id.id, l.product_id.id, l.quantity, l.price_unit, round(l.price_subtotal, 2), l.display_type,
                           l.name, l.lote, l.peso_liquido, l.peso_bruto, l.volume, l.caixas, str(l.data_validade), l.tax_ids.ids]
for m in env["account.move"].sudo().search([("primavera_ref", "!=", False)]):
    out["faturas"][m.primavera_ref] = [m.id, m.state, round(m.amount_untaxed, 2), round(m.amount_tax, 2), round(m.amount_total, 2),
                                       m.partner_id.id, m.ecl_sale_order_id.id, m.name]
for model in ["packing.list", "declaracao.lote", "certificado.salubridade", "certificado.qualidade", "boletim.analises"]:
    for r in env[model].sudo().search([]):
        lines = getattr(r, "line_ids", env[model])
        h = hashlib.md5(json.dumps([[str(v) for v in l.read([f for f in l._fields if f not in ("write_date", "write_uid", "__last_update")])[0].values()] for l in lines], sort_keys=True).encode()).hexdigest() if lines else ""
        out["docs"][f"{model}:{r.id}"] = [r.name, r.state, r.fatura_id.id if "fatura_id" in r._fields else None, h]
json.dump(out, open(f"/out/{NOME}.json", "w"), default=str)
print("R foto", NOME, {k: len(v) for k, v in out.items()})
