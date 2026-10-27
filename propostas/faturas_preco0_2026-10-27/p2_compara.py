"""Compara fotografias (p2_foto.py) e totais com o Primavera. Uso: p2_compara.py antes depois [verificar_primavera]"""
import json
import sys
from collections import Counter
D = "/home/odoo/.claude/jobs/738b98e4/tmp/out/"
a, b = json.load(open(D + sys.argv[1] + ".json")), json.load(open(D + sys.argv[2] + ".json"))
corr = {str(x["line"]): x for x in json.load(open(D + "p2_corr_draft.json"))}
tot = json.load(open(D + "p2_tot.json"))
# linhas
mud = Counter(); fora = []
for lid in set(a["linhas"]) | set(b["linhas"]):
    la, lb = a["linhas"].get(lid), b["linhas"].get(lid)
    if la == lb:
        continue
    if la is None or lb is None:
        fora.append((lid, "linha criada/apagada")); continue
    campos = [i for i, (x, y) in enumerate(zip(la, lb)) if x != y]
    if lid in corr and set(campos) <= {3, 4}:
        mud["linha corrigida (preço/subtotal)"] += 1
    elif set(campos) <= {4} and la[5] == "tax":
        mud["linha de imposto recalculada"] += 1
    else:
        fora.append((lid, campos, la, lb))
print("ALTERAÇÕES EM LINHAS:", dict(mud), "| FORA DO ESPERADO:", len(fora), fora[:5])
# faturas
fat_mud = [r for r in a["faturas"] if a["faturas"][r] != b["faturas"].get(r)]
refs_corr = {x["ref"] for x in corr.values()}
outras = [r for r in fat_mud if r not in refs_corr]
nao_tot = [r for r in fat_mud if r in refs_corr and [a["faturas"][r][i] for i in (0, 1, 5, 6, 7)] != [b["faturas"][r][i] for i in (0, 1, 5, 6, 7)]]
print("FATURAS com totais alterados:", len(fat_mud), "| fora das 396:", outras[:5], "| com outros campos alterados:", nao_tot[:5])
print("DOCUMENTOS alterados:", [k for k in a["docs"] if a["docs"][k] != b["docs"].get(k)][:5], "| total documentos", len(a["docs"]), "→", len(b["docs"]))
if len(sys.argv) > 3:
    cmp = Counter(); exemplos = []
    for r in refs_corr:
        t, o = tot[r], b["faturas"][r][2]
        bruto = round(t["merc"] + t["outros"], 2)
        if abs(o - bruto) <= 0.01:
            cmp["igual ao Primavera (sem desconto)" if not t["tem_desconto"] else "igual ao bruto (falta só o desconto — ponto 3)"] += 1
        else:
            cmp["DIFERENTE"] += 1; exemplos.append((r, o, bruto))
    print("396 FATURAS CORRIGIDAS vs PRIMAVERA:", dict(cmp), exemplos[:5])
