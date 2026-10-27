# Só leitura: verificação dos descontos das ECLs (SQL Primavera) vs Odoo, com o código instalado.
c = env["primavera.connection"].browse(1)
prim, series = c._verify_ecls_primavera()
SO = env["sale.order"].sudo().with_context(active_test=False)
n = 0; dif = []; outras = []
for ref, p in prim.items():
    so = SO.search([("primavera_ecl_ref", "=", ref)], limit=1)
    if not so or p["anulada"]:
        continue
    n += 1
    d = c._verify_ecl_diffs(so, p)
    dif += [(ref, x) for x in d if "desconto" in x]
    outras += [(ref, x) for x in d if "desconto" not in x]
print("R ECLs comparadas:", n, "| diferenças de desconto:", len(dif), dif[:5])
print("R outras diferenças (já existentes, não relacionadas):", len(outras), outras[:5])
env.cr.rollback()
