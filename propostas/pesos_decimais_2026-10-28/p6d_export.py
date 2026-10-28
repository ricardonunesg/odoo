import json
c = env["primavera.connection"].browse(1); conn = c._sql_connection(); cur = conn.cursor()
cur.execute("SELECT @@DBTS"); ver = bytes(cur.fetchone()[0]).hex()
cur.execute("SELECT Artigo, Descricao, ArtigoAnulado, UnidadeBase, UnidadeVenda, UnidadeCompra, Peso, PesoLiquido, Volume, CodBarras, Observacoes FROM Artigo")
cols = [d[0] for d in cur.description]; rows = [dict(zip(cols, r)) for r in cur.fetchall()]
json.dump({"rows": rows, "ver": ver}, open("/tmp/p6d_rows.json", "w"), default=str)
print("R linhas", len(rows), "| com PesoLiquido", sum(1 for r in rows if r["PesoLiquido"]))
