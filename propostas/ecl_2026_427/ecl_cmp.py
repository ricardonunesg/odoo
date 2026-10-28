import json
c = env["primavera.connection"].browse(1); cur = c._sql_connection().cursor()
cur.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME LIKE '%Hist%Doc%' OR TABLE_NAME LIKE '%Doc%Hist%' OR TABLE_NAME LIKE 'Log%Doc%' OR TABLE_NAME LIKE '%Auditoria%'")
print("R tabelas de histórico:", [r[0] for r in cur.fetchall()][:20])
cur.execute("""SELECT cd.Serie, cd.NumDoc, cd.Entidade, cd.Nome, ISNULL(cs.Anulado,0), cd.DataUltimaActualizacao, cd.Data FROM CabecDoc cd LEFT JOIN CabecDocStatus cs ON cs.IdCabecDoc=cd.Id
  WHERE cd.TipoDoc='ECL' AND cd.Serie IN ('2025','2026')""")
P = {f"ECL/{r[0].strip()}/{r[1]}": (r[2].strip() if r[2] else None, r[3], bool(r[4]), str(r[5])[:16], str(r[6])[:16]) for r in cur.fetchall()}
SO = env["sale.order"].sudo().with_context(active_test=False)
dif = []; falta = []; n = 0
for so in SO.search([("primavera_ecl_ref", "!=", False)]):
    p = P.get(so.primavera_ecl_ref)
    if not p:
        falta.append(so.primavera_ecl_ref); continue
    n += 1
    code = so.partner_id.commercial_partner_id.primavera_customer_code or so.partner_id.primavera_customer_code
    if code != p[0]:
        dif.append((so.primavera_ecl_ref, so.state, so.stage_id.name, "Odoo:", code, so.partner_id.name, "| Primavera:", p[0], p[1], "| anulada" if p[2] else "", "| criada Odoo", str(so.create_date)[:16], "| alterada Prim", p[3],
                    "| faturas", so.primavera_fatura_refs or "-"))
print("R ECLs comparadas:", n, "| no Odoo sem correspondência no Primavera:", falta[:10])
print("R com cliente diferente:", len(dif))
for d in dif: print("R   ", *d)
o = set(SO.search([("primavera_ecl_ref", "=like", "ECL/2026/%")]).mapped("primavera_ecl_ref"))
print("R ECLs 2026 do Primavera que não estão no Odoo:", len([k for k in P if k.startswith("ECL/2026/") and k not in o]))
env.cr.rollback()
