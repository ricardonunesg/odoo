# Só leitura: dados reais para o ensaio do ponto 6 (artigos SQL + WebAPI das ECLs em curso).
import json
c = env["primavera.connection"].browse(1)
res = c._fetch_sql_products()
rows, ver = res
SO = env["sale.order"].sudo()
ecls = SO.search(c._ecl_resync_domain())
api = {}
filial = c.api_filial or "000"
for so in ecls:
    ref = so.primavera_ecl_ref
    p = (ref or "").split("/")
    if len(p) == 3:
        api[ref] = c._edita(f"/v2/Vendas/Docs/Edita/{filial}/ECL/{p[1]}/{p[2]}", strict=True)
arts = {}
for d in api.values():
    for l in (d or {}).get("Linhas") or []:
        a = (l.get("Artigo") or "").strip()
        if a and a not in arts:
            arts[a] = c._edita(f"/v2/Base/Artigos/Edita/{a}")
json.dump({"rows": rows, "ver": ver, "ecl": api, "art": arts}, open("/tmp/p6_data.json", "w"), default=str)
print("R artigos SQL", len(rows), "| ECLs em curso", len(ecls), "| respostas", sum(1 for v in api.values() if v), "| artigos API", len(arts))
