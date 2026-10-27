from odoo.tools import float_round
c = env['primavera.connection'].browse(1)
print("R método de arredondamento do IVA no Odoo:", env.company.tax_calculation_rounding_method)
cur = c._sql_connection().cursor()
def doc(ref):
    t, s, n = ref.split('/')
    cur.execute("""SELECT c.TotalMerc, c.TotalDesc, c.TotalIva, c.TotalDocumento FROM CabecDoc c WHERE c.TipoDoc=%s AND c.Serie=%s AND c.NumDoc=%s""", (t, s, int(n)))
    merc, tdesc, tiva, tdoc = [float(x or 0) for x in cur.fetchone()]
    cur.execute("""SELECT l.Artigo, l.Quantidade, l.PrecUnit, ISNULL(l.Desconto1,0), l.TotalIliquido, l.TotalDA, l.PrecoLiquido, l.TaxaIva, l.TotalIva
                   FROM CabecDoc c JOIN LinhasDoc l ON l.IdCabecDoc=c.Id WHERE c.TipoDoc=%s AND c.Serie=%s AND c.NumDoc=%s
                     AND l.Artigo IS NOT NULL AND LTRIM(l.Artigo)<>'' ORDER BY l.NumLinha""", (t, s, int(n)))
    print(f"R ===== {ref} | Primavera: mercadoria {merc:.2f} − descontos {tdesc:.2f} = {merc - tdesc:.2f} | IVA {tiva:.2f}")
    soma_o = soma_iva_o_linha = 0.0; base_por_taxa = {}
    for art, q, pu, d1, tili, tda, pliq, taxa, liva in cur.fetchall():
        q, pu, d1, tili, tda, pliq, taxa, liva = map(float, (q, pu, d1, tili, tda, pliq, taxa, liva))
        exacto = q * pu * (1 - d1 / 100)
        sub_o = float_round(exacto, 2)
        soma_o += sub_o
        soma_iva_o_linha += float_round(sub_o * taxa / 100, 2)
        base_por_taxa[taxa] = base_por_taxa.get(taxa, 0) + sub_o
        print(f"R  {art}: {q:g} × {pu:g} = {tili:.2f} bruto | desconto {d1:g}%")
        print(f"R     Primavera: {tili:.2f} − desconto {tda:.2f} (= {q * pu * d1 / 100:.4f} arredondado) = {pliq:.2f} | IVA {taxa:g}% = {liva:.2f}")
        print(f"R     Odoo:      {q:g} × {pu:g} × {1 - d1 / 100:g} = {exacto:.4f} → {sub_o:.2f}  (diferença {sub_o - pliq:+.2f})")
    iva_global = sum(float_round(b * t / 100, 2) for t, b in base_por_taxa.items())
    print(f"R  TOTAL Odoo sem IVA {soma_o:.2f} (Primavera {merc - tdesc:.2f}) | IVA Odoo por linha {soma_iva_o_linha:.2f} / global {iva_global:.2f} (Primavera {tiva:.2f})")
doc('FA/2026/18')
doc('ECL/2026/228')
