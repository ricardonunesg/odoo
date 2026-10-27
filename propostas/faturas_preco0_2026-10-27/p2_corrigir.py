# Ponto 2: linhas de faturas (rascunho) com preço 0 no Primavera que entraram a 1 € → 0 €.
# Lê /out/p2_corr_draft.json (linha, fatura, artigo, de, para). Verifica TUDO antes de mexer:
# fatura em rascunho, artigo igual, preço actual = 'de'. Se alguma falhar, não altera nada.
# MODO = "corrigir" (1 → 0) ou "reverter" (0 → 1).
import json
from collections import defaultdict
MODO = "__MODO__"
corr = json.load(open("/out/p2_corr_draft.json"))
AML = env["account.move.line"].sudo()
problemas, por_fatura = [], defaultdict(list)
for x in corr:
    l = AML.browse(x["line"]).exists()
    esperado, novo = (x["de"], x["para"]) if MODO == "corrigir" else (x["para"], x["de"])
    if not l:
        problemas.append((x["ref"], x["line"], "linha não existe")); continue
    if l.move_id.primavera_ref != x["ref"] or l.move_id.state != "draft":
        problemas.append((x["ref"], x["line"], "fatura diferente ou não está em rascunho", l.move_id.primavera_ref, l.move_id.state)); continue
    if l.product_id.default_code != x["art"]:
        problemas.append((x["ref"], x["line"], "artigo diferente", l.product_id.default_code)); continue
    if l.price_unit != esperado:
        problemas.append((x["ref"], x["line"], f"preço {l.price_unit} ≠ {esperado}")); continue
    por_fatura[l.move_id].append((l.id, novo))
if problemas:
    print("R CANCELADO, nada alterado. Problemas:", len(problemas), problemas[:10])
else:
    for move, lst in por_fatura.items():
        move.write({"invoice_line_ids": [(1, lid, {"price_unit": p}) for lid, p in lst]})
    env.cr.commit()
    print("R OK:", MODO, sum(len(v) for v in por_fatura.values()), "linhas em", len(por_fatura), "faturas")
