import json
from collections import defaultdict
from odoo.tools import float_round
c = env['primavera.connection'].browse(1)
corr = {x["line"]: x["para"] for x in json.load(open("/tmp/p3_corr.json")) if x["modelo"] == "account.move.line"}
refs = sorted({x_ref for x_ref in env['account.move.line'].browse(list(corr)).mapped('move_id.primavera_ref')})
cur = c._sql_connection().cursor()
for ref in refs:
    t, s, n = ref.split('/')
    cur.execute("SELECT TotalMerc - ISNULL(TotalDesc,0) + ISNULL(TotalOutros,0), TotalIva FROM CabecDoc WHERE TipoDoc=%s AND Serie=%s AND NumDoc=%s", (t, s, int(n)))
    p_liq, p_iva = map(float, cur.fetchone())
    cur.execute("""SELECT l.Artigo, l.PrecoLiquido, l.TaxaIva, l.TotalIva FROM CabecDoc c JOIN LinhasDoc l ON l.IdCabecDoc=c.Id
                   WHERE c.TipoDoc=%s AND c.Serie=%s AND c.NumDoc=%s AND (ISNULL(l.PrecoLiquido,0)<>0 OR ISNULL(l.TotalIva,0)<>0) ORDER BY l.NumLinha""", (t, s, int(n)))
    plines = [(a, float(pl), float(tx), float(iv)) for a, pl, tx, iv in cur.fetchall()]
    m = env['account.move'].search([('primavera_ref', '=', ref)])
    base = defaultdict(float); base_r = {}; olines = []
    for l in m.invoice_line_ids.filtered(lambda l: l.display_type == 'product'):
        disc = corr.get(l.id, l.discount)
        sub = float_round(l.quantity * l.price_unit * (1 - disc / 100), 2)
        rate = sum(l.tax_ids.mapped('amount'))
        base[rate] += l.quantity * l.price_unit * (1 - disc / 100)
        base_r[rate] = base_r.get(rate, 0) + sub
        if sub:
            olines.append((l.product_id.default_code, sub, rate))
    o_liq = sum(base_r.values()); o_iva = sum(float_round(b * r / 100, 2) for r, b in base.items())
    if abs(o_liq - p_liq) < 0.005 and abs(o_iva - p_iva) >= 0.005 and abs(o_iva - p_iva) <= 0.02:
        print(f"R ===== {ref}: sem IVA Odoo {o_liq:.2f} / Primavera {p_liq:.2f} | IVA Odoo {o_iva:.2f} / Primavera {p_iva:.2f}")
        for (a, pl, tx, iv), (ao, so, ro) in zip(plines, olines):
            print(f"R   {a}: Primavera {pl:.2f} × {tx:g}% = {pl * tx / 100:.4f} → {iv:.2f} | Odoo {so:.2f} × {ro:g}%")
        for r, b in base.items():
            print(f"R   Odoo: base por arredondar {b:.4f} × {r:g}% = {b * r / 100:.4f} → {float_round(b * r / 100, 2):.2f} (sobre a base arredondada {base_r[r]:.2f} daria {float_round(base_r[r] * r / 100, 2):.2f})")
