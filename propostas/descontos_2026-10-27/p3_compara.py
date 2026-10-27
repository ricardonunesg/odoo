"""Compara fotografias p3 e valida contra o Primavera. Uso: p3_compara.py antes depois [primavera] [por_valores]"""
import json
import sys
from collections import Counter, defaultdict
D = "/home/odoo/.claude/jobs/738b98e4/tmp/out/"
a, b = json.load(open(D + sys.argv[1] + ".json")), json.load(open(D + sys.argv[2] + ".json"))
corr = {(x["modelo"], str(x["line"])): x for x in json.load(open(D + "p3_corr.json"))}
tot = json.load(open(D + "p3_dados.json"))["tot"]
opts = sys.argv[3:]
if "por_valores" not in opts:
    for chave, modelo in (("aml", "account.move.line"), ("sol", "sale.order.line")):
        mud = Counter(); fora = []
        for lid in set(a[chave]) | set(b[chave]):
            la, lb = a[chave].get(lid), b[chave].get(lid)
            if la == lb:
                continue
            if la is None or lb is None:
                fora.append((lid, "linha criada/apagada", (la or lb)[6], (la or lb)[0])); continue
            campos = {i for i, (x, y) in enumerate(zip(la, lb)) if x != y}
            if (modelo, lid) in corr and campos <= {4, 5}:
                mud["linha corrigida (desconto/subtotal)"] += 1
            elif campos <= {5} and la[6] == "tax":
                mud["linha de imposto recalculada"] += 1
            else:
                fora.append((lid, sorted(campos), la, lb))
        print(f"LINHAS {modelo}:", dict(mud), "| FORA DO ESPERADO:", len(fora), Counter((f[1], f[2]) if f[1] == "linha criada/apagada" else "outro" for f in fora), [f for f in fora if f[1] != "linha criada/apagada"][:3])
else:
    # nova sincronização recria linhas: comparar por documento os valores das linhas de artigo
    for chave in ("aml", "sol"):
        def por_doc(f):
            d = defaultdict(list)
            for v in f[chave].values():
                if v[1] and v[6] in ("product", "False", False, None) and v[0] in tot:
                    d[v[0]].append((v[1], v[2], v[3], v[4], v[5]))
            return {k: sorted(x) for k, x in d.items()}
        pa, pb = por_doc(a), por_doc(b)
        dif = [k for k in pa if pa[k] != pb.get(k)]
        print(f"VALORES DAS LINHAS ({chave}) depois da nova sincronização: documentos iguais {len(pa) - len(dif)} / {len(pa)}", dif[:5])
refs_corr = {x["ref"] for x in corr.values()}
fat_out = [r for r in a["fat"] if a["fat"][r] != b["fat"].get(r) and r not in refs_corr]
ecl_out = [r for r in a["ecl"] if a["ecl"][r] != b["ecl"].get(r) and r not in refs_corr]
ecl_campos = [r for r in refs_corr if r in a["ecl"] and [a["ecl"][r][i] for i in (0, 1, 2, 5, 6, 7)] != [b["ecl"][r][i] for i in (0, 1, 2, 5, 6, 7)]]
fat_campos = [r for r in refs_corr if r in a["fat"] and [a["fat"][r][i] for i in (0, 1, 4, 5)] != [b["fat"][r][i] for i in (0, 1, 4, 5)]]
print("OUTROS DOCUMENTOS alterados — faturas:", fat_out[:5], "| ECLs:", ecl_out[:5], "| cabeçalhos alterados nas corrigidas:", fat_campos[:5], ecl_campos[:5])
print("DOCUMENTOS ASSOCIADOS alterados:", [k for k in a["docs"] if a["docs"][k] != b["docs"].get(k)][:5], "| total", len(a["docs"]), "→", len(b["docs"]))
if "primavera" in opts:
    for nome, grupo, iu, it in (("FATURAS", "fat", 2, 3), ("ECLs", "ecl", 3, 4)):
        c = Counter(); ex = []
        for r, t in tot.items():
            if r not in b[grupo]:
                continue
            du = round(b[grupo][r][iu] - t["liq"], 2); di = round(b[grupo][r][it] - t["iva"], 2)
            k = "sem IVA: " + ("igual" if abs(du) < 0.005 else ("±1–2 cêntimos" if abs(du) <= 0.02 else "DIFERENTE"))
            k += " | IVA: " + ("igual" if abs(di) < 0.005 else ("±1–2 cêntimos" if abs(di) <= 0.02 else "DIFERENTE"))
            c[k] += 1
            if "DIFERENTE" in k:
                ex.append((r, b[grupo][r][iu], t["liq"], b[grupo][r][it], t["iva"]))
        print(f"{nome} vs PRIMAVERA:", dict(c), ex[:6])
