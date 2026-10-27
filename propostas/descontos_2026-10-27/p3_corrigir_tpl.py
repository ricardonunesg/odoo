# Ponto 3: descontos de linha/cliente do Primavera nas linhas existentes (faturas em rascunho e ECLs).
# Lê LISTA (json: modelo, linha, ref, artigo, de, para). Verifica TUDO antes de mexer; se algo falhar não altera nada.
# MODO = "corrigir" (de → para) ou "reverter" (para → de).
import json
from collections import defaultdict
MODO = "__MODO__"
LISTA = "__LISTA__"
assert MODO in ("corrigir", "reverter"), "MODO inválido"
corr = json.load(open(LISTA))
problemas, por_doc = [], defaultdict(list)
for x in corr:
    l = env[x["modelo"]].sudo().browse(x["line"]).exists()
    esperado, novo = (x["de"], x["para"]) if MODO == "corrigir" else (x["para"], x["de"])
    if not l:
        problemas.append((x["ref"], x["line"], "linha não existe")); continue
    doc = l.move_id if x["modelo"] == "account.move.line" else l.order_id
    ref = doc.primavera_ref if x["modelo"] == "account.move.line" else doc.primavera_ecl_ref
    if ref != x["ref"]:
        problemas.append((x["ref"], x["line"], "documento diferente", ref)); continue
    if x["modelo"] == "account.move.line" and doc.state != "draft":
        problemas.append((x["ref"], x["line"], "fatura não está em rascunho", doc.state)); continue
    if x["modelo"] == "sale.order.line" and doc.state == "cancel":
        problemas.append((x["ref"], x["line"], "ECL cancelada")); continue
    if l.product_id.default_code != x["art"]:
        problemas.append((x["ref"], x["line"], "artigo diferente", l.product_id.default_code)); continue
    if abs((l.discount or 0.0) - esperado) > 1e-9:
        problemas.append((x["ref"], x["line"], f"desconto {l.discount} ≠ {esperado}")); continue
    por_doc[doc].append((l.id, novo))
if problemas:
    print("R CANCELADO, nada alterado. Problemas:", len(problemas), problemas[:10])
else:
    for doc, lst in por_doc.items():
        campo = "invoice_line_ids" if doc._name == "account.move" else "order_line"
        doc.write({campo: [(1, lid, {"discount": d}) for lid, d in lst]})
    env.cr.commit()
    print("R OK:", MODO, sum(len(v) for v in por_doc.values()), "linhas em", len(por_doc), "documentos",
          dict((k, sum(1 for d in por_doc if d._name == k)) for k in ("account.move", "sale.order")))
