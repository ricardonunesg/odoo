c = env["primavera.connection"].browse(1); cur = c._sql_connection().cursor()
cur.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='Auditorias'")
cols = [r[0] for r in cur.fetchall()]; print("R Auditorias colunas:", cols)
try:
    cur.execute("SELECT TOP 20 * FROM Auditorias WHERE CAST(Descricao AS NVARCHAR(4000)) LIKE '%ECL%427%' OR CAST(Chave AS NVARCHAR(400)) LIKE '%427%' ORDER BY 1 DESC")
    cc = [d[0] for d in cur.description]
    for r in cur.fetchall(): print("R  ", {k: str(v)[:120] for k, v in zip(cc, r) if v not in (None, "")})
except Exception as e:
    print("R auditoria:", str(e)[:200])
cur.execute("""SELECT cd.NumDoc, cd.Entidade, cd.Nome, cd.Data, ISNULL(cs.Anulado,0) FROM CabecDoc cd LEFT JOIN CabecDocStatus cs ON cs.IdCabecDoc=cd.Id WHERE cd.TipoDoc='ECL' AND cd.Serie='2026'""")
o = set(env["sale.order"].sudo().with_context(active_test=False).search([("primavera_ecl_ref", "=like", "ECL/2026/%")]).mapped("primavera_ecl_ref"))
print("R ECLs 2026 em falta no Odoo:", [(r[0], r[1], r[2], str(r[3])[:16], "anulada" if r[4] else "activa") for r in cur.fetchall() if f"ECL/2026/{r[0]}" not in o])
env.cr.rollback()
