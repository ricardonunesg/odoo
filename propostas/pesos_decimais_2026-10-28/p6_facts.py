# Ponto 6 — só leitura: precisão e unidades no Primavera vs Odoo.
from decimal import Decimal
from collections import Counter
c = env["primavera.connection"].browse(1)
conn = c._sql_connection(); cur = conn.cursor()
cur.execute("""SELECT COLUMN_NAME, DATA_TYPE, NUMERIC_PRECISION, NUMERIC_SCALE FROM INFORMATION_SCHEMA.COLUMNS
 WHERE TABLE_NAME='Artigo' AND (COLUMN_NAME LIKE '%Peso%' OR COLUMN_NAME LIKE '%Volume%' OR COLUMN_NAME LIKE 'Unidade%'
 OR COLUMN_NAME LIKE '%Massa%' OR COLUMN_NAME LIKE '%Capacidade%' OR COLUMN_NAME LIKE '%Dimens%' OR COLUMN_NAME LIKE '%Comprimento%' OR COLUMN_NAME LIKE '%Largura%' OR COLUMN_NAME LIKE '%Altura%')""")
print("R colunas Artigo:", cur.fetchall())
cur.execute("""SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, NUMERIC_PRECISION, NUMERIC_SCALE FROM INFORMATION_SCHEMA.COLUMNS
 WHERE TABLE_NAME IN ('LinhasDoc','LinhasDocTrans','CabecDoc') AND (COLUMN_NAME LIKE '%Peso%' OR COLUMN_NAME LIKE '%Volume%' OR COLUMN_NAME LIKE '%Massa%')""")
print("R colunas documentos:", cur.fetchall())
cur.execute("SELECT Artigo, Peso, Volume, UnidadeBase, UnidadeVenda, UnidadeCompra, ArtigoAnulado FROM Artigo")
prim = {r[0].strip(): r for r in cur.fetchall()}
try:
    cur.execute("SELECT Artigo, UnidadePeso, UnidadeVolume FROM Artigo"); un = {r[0].strip(): r[1:] for r in cur.fetchall()}
    print("R unidades peso/volume no Primavera:", Counter(un.values()).most_common(10))
except Exception as e:
    print("R sem colunas UnidadePeso/UnidadeVolume:", str(e)[:100]); conn.close(); conn = c._sql_connection(); cur = conn.cursor()
def casas(x):
    if x is None: return 0
    d = Decimal(str(x)).normalize(); return max(0, -d.as_tuple().exponent)
cp = Counter(casas(r[1]) for r in prim.values()); cv = Counter(casas(r[2]) for r in prim.values())
print("R Primavera artigos:", len(prim), "| casas decimais peso:", sorted(cp.items()), "| volume:", sorted(cv.items()))
print("R tipos python:", type(next(iter(prim.values()))[1]).__name__)
PT = env["product.product"].sudo().with_context(active_test=False)
odoo = {p.default_code: p for p in PT.search([("default_code", "!=", False)])}
env.cr.execute("select pp.default_code, pt.weight::text, pt.volume::text from product_product pp join product_template pt on pt.id=pp.product_tmpl_id where pp.default_code is not null")
raw = {r[0]: (r[1], r[2]) for r in env.cr.fetchall()}
dif_p, dif_v, falta = [], [], []
for code, r in prim.items():
    if code not in raw:
        falta.append(code); continue
    wp, vp = Decimal(str(r[1] or 0)), Decimal(str(r[2] or 0))
    wo, vo = Decimal(raw[code][0] or 0), Decimal(raw[code][1] or 0)
    if wp != wo: dif_p.append((code, str(r[1]), raw[code][0]))
    if vp != vo: dif_v.append((code, str(r[2]), raw[code][1]))
print("R sem artigo no Odoo:", len(falta), falta[:10])
print("R pesos diferentes:", len(dif_p), dif_p[:15])
print("R volumes diferentes:", len(dif_v), dif_v[:15])
print("R Odoo artigos com peso>0:", sum(1 for v in raw.values() if v[0] and Decimal(v[0])), "| com volume>0:", sum(1 for v in raw.values() if v[1] and Decimal(v[1])))
print("R exemplos 4-5 casas:", [(k, str(r[1]), raw.get(k, ("-",))[0]) for k, r in prim.items() if casas(r[1]) >= 4][:10])
print("R exemplos volume >5 casas:", [(k, str(r[2]), raw.get(k, ("-", "-"))[1]) for k, r in prim.items() if casas(r[2]) > 5][:8])
# unidades
cu = Counter((r[3], r[4], r[5]) for r in prim.values())
print("R unidades base/venda/compra mais comuns:", cu.most_common(15))
uoms = env["uom.uom"].sudo().with_context(active_test=False).search([])
print("R uom Odoo:", [(u.name, u.category_id.name, u.uom_type, round(u.factor, 6), u.rounding) for u in uoms][:60])
print("R uom peso/volume ICP:", env["ir.config_parameter"].sudo().get_param("product.weight_in_lbs"), env["ir.config_parameter"].sudo().get_param("product.volume_in_cubic_feet"))
print("R campos digits: weight", PT._fields["weight"].get_digits(env), "volume", PT._fields["volume"].get_digits(env))
conn.close()
