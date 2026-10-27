import json
from odoo.tools import float_round
c = env['primavera.connection'].browse(1)
cur = c._sql_connection().cursor()
cur.execute("""SELECT l.Artigo, l.Quantidade, l.PrecUnit, l.Desconto1, l.PrecoLiquido, l.CodIva, l.TaxaIva, l.TotalIva
               FROM CabecDoc c JOIN LinhasDoc l ON l.IdCabecDoc=c.Id WHERE c.TipoDoc='FA' AND c.Serie='2026' AND c.NumDoc=176 ORDER BY l.NumLinha""")
print("R Primavera linhas:", [(a, float(q or 0), float(p or 0), float(d or 0), float(pl or 0), ci, float(tx or 0), float(iv or 0)) for a, q, p, d, pl, ci, tx, iv in cur.fetchall() if a or pl])
cur.execute("SELECT TotalMerc - ISNULL(TotalDesc,0), TotalIva FROM CabecDoc WHERE TipoDoc='FA' AND Serie='2026' AND NumDoc=176")
print("R Primavera totais (sem IVA, IVA):", [float(x) for x in cur.fetchone()])
m = env['account.move'].search([('primavera_ref', '=', 'FA/2026/176')])
print("R Odoo HOJE: estado", m.state, "| sem IVA", m.amount_untaxed, "| IVA", m.amount_tax, "| criada", m.create_date, "| última escrita", m.write_date)
for l in m.invoice_line_ids.filtered(lambda l: l.display_type == 'product' and l.price_unit):
    print("R   linha", l.product_id.default_code, l.quantity, l.price_unit, "desc", l.discount, "| IVA no Odoo:", l.tax_ids.mapped('name'))
corr = {x["line"]: x["para"] for x in json.load(open("/tmp/p3_corr.json")) if x["ref"] == "FA/2026/176"}
base = sum(l.quantity * l.price_unit * (1 - corr.get(l.id, l.discount) / 100) for l in m.invoice_line_ids.filtered(lambda l: l.display_type == 'product'))
print("R Odoo DEPOIS da correcção dos descontos (simulado): sem IVA", float_round(base, 2), "| IVA a 23%", float_round(base * 0.23, 2))
msgs = env['mail.message'].search([('model', '=', 'account.move'), ('res_id', '=', m.id)], order='id')
print("R histórico da fatura:", [(str(x.date)[:16], (x.body or '')[:60]) for x in msgs][:5])
