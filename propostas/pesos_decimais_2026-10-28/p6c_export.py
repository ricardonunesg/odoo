import json
c = env["primavera.connection"].browse(1); f = c.api_filial or "000"
out = {"fat": {}, "art": {}}
for t, s, n in (("FA", "2026", 171), ("FAT", "2026", 47)):
    d = c._edita(f"/v2/Vendas/Docs/Edita/{f}/{t}/{s}/{n}", strict=True)
    out["fat"][f"{t}/{s}/{n}"] = d
    for l in (d or {}).get("Linhas") or []:
        a = (l.get("Artigo") or "").strip()
        if a and a not in out["art"]:
            out["art"][a] = c._edita(f"/v2/Base/Artigos/Edita/{a}")
json.dump(out, open("/tmp/p6c_data.json", "w"), default=str)
print("R faturas", {k: [(l.get("Artigo"), l.get("Quantidade"), l.get("Unidade"), l.get("IntrastatMassaLiq")) for l in (v or {}).get("Linhas") or [] if l.get("Artigo")] for k, v in out["fat"].items()})
print("R artigos", {k: (v or {}).get("Peso") and ((v or {}).get("Peso"), (v or {}).get("PesoLiquido"), (v or {}).get("UnidadeVenda")) for k, v in out["art"].items()})
