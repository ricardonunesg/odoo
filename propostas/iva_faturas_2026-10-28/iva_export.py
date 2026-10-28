import json
c = env["primavera.connection"].browse(1); f = c.api_filial or "000"; cur = c._sql_connection().cursor()
cur.execute("""SELECT cd.TipoDoc, cd.Serie, cd.NumDoc, cd.TotalMerc, cd.TotalDesc, cd.TotalIva, cd.TotalDocumento, cd.TotalOutros, ISNULL(cs.Anulado,0)
  FROM CabecDoc cd LEFT JOIN CabecDocStatus cs ON cs.IdCabecDoc=cd.Id WHERE cd.TipoDoc IN ('FA','FAT') AND cd.Serie='2026'""")
H = {f"{r[0]}/{r[1]}/{r[2]}": dict(iva=float(r[5] or 0), total=float(r[6] or 0), anulado=bool(r[8])) for r in cur.fetchall()}
cur.execute("""SELECT r.TipoDoc, r.Serie, r.NumDoc, r.CodIva, r.TaxaIva, r.Incidencia, r.Valor FROM ResumoIva r WHERE r.TipoDoc IN ('FA','FAT') AND r.Serie='2026' AND r.Modulo='V'""")
RI = {}
for r in cur.fetchall():
    RI.setdefault(f"{r[0]}/{r[1]}/{r[2]}", []).append((r[3], float(r[4] or 0), round(float(r[5] or 0), 2), round(float(r[6] or 0), 2)))
api = {}
for k in H:
    t, s, n = k.split("/")
    api[k] = c._edita(f"/v2/Vendas/Docs/Edita/{f}/{t}/{s}/{n}", strict=True)
arts = {}
for d in api.values():
    for l in (d or {}).get("Linhas") or []:
        a = (l.get("Artigo") or "").strip()
        if a and a not in arts:
            arts[a] = c._edita(f"/v2/Base/Artigos/Edita/{a}")
json.dump({"H": H, "RI": RI, "api": api, "art": arts}, open("/tmp/iva_data.json", "w"), default=str)
print("R faturas", len(H), "| respostas API", sum(1 for v in api.values() if v), "| artigos", len(arts), "| docs com ResumoIva SQL", len(RI))
