import logging
import re
from datetime import date, timedelta

from odoo import _, fields, models
from odoo.exceptions import AccessError

from odoo.addons.primavera_connector.models.primavera_connection import vat_ficticio

_logger = logging.getLogger(__name__)

# Faturas de venda (SAF-T FT/FR/FS). Ficam de fora adiantamentos (FAA, FAAT),
# pró-formas (FP), faturas de imobilizado (FM) e notas de débito (ND).
TIPOS_FATURA = ("FA", "FAT", "FR", "FRT", "FS")
# Notas de crédito (SAF-T NC): devoluções/regularizações (NC, NCT), descontos
# (NCDA, NCDT) e estornos de fatura-recibo (DFRT). Ficam de fora as NCAA/NCAT,
# que só anulam adiantamentos (FAA/FAAT): a fatura final já tem a venda toda.
# No Primavera estes documentos já têm valores e quantidades negativos.
TIPOS_NOTA_CREDITO = ("NC", "NCT", "NCDA", "NCDT", "DFRT")
TIPOS = TIPOS_FATURA + TIPOS_NOTA_CREDITO
# Linhas de comentário (sem valores) não são mostradas.
TIPO_LINHA_COMENTARIO = "60"

# Só SELECT. Validado em todas as faturas e notas de crédito 2025–2026 (10/11/2026):
#   TotalMerc − TotalDesc + TotalOutros = TotalDocumento − TotalIva = Σ PrecoLiquido
# PrecUnit × Quantidade = TotalIliquido (em valor absoluto) → PrecUnit é o preço
# ANTES dos descontos; PrecoLiquido é o valor da linha já com o desconto de linha
# (TotalDA) e a parte do desconto global do cliente (TotalDC) e financeiro (TotalDF).
_WHERE = (
    "c.TipoEntidade = 'C' AND c.Entidade = %s "
    f"AND c.TipoDoc IN ({', '.join(repr(t) for t in TIPOS)}) "
    "AND ISNULL(s.Anulado, 0) = 0 AND c.Data >= %s AND c.Data < %s"
)
SQL_DOCUMENTOS = (
    "SELECT c.Id, c.TipoDoc, c.Serie, c.NumDoc, c.Data, c.Moeda, "
    "c.TotalMerc, c.TotalDesc, c.TotalOutros, c.TotalIva, c.TotalDocumento, "
    "c.DescEntidade, c.DescPag "
    "FROM CabecDoc c JOIN CabecDocStatus s ON s.IdCabecDoc = c.Id "
    f"WHERE {_WHERE} ORDER BY c.Data DESC, c.NumDoc DESC"
)
SQL_LINHAS = (
    "SELECT l.IdCabecDoc, l.Id, l.NumLinha, l.Artigo, l.Descricao, l.Quantidade, l.Unidade, "
    "l.PrecUnit, l.Desconto1, l.Desconto2, l.Desconto3, "
    "l.TotalDA, l.TotalDC, l.TotalDF, l.PrecoLiquido "
    "FROM LinhasDoc l JOIN CabecDoc c ON c.Id = l.IdCabecDoc "
    "JOIN CabecDocStatus s ON s.IdCabecDoc = c.Id "
    f"WHERE {_WHERE} AND ISNULL(l.TipoLinha, '') <> '{TIPO_LINHA_COMENTARIO}' "
    "ORDER BY l.NumLinha"
)
SQL_CLIENTE = "SELECT Cliente, Nome, NumContrib, ClienteAnulado FROM Clientes WHERE Cliente = %s"


def _nif(vat):
    """NIF normalizado (sem prefixo ISO do país), ou "" se fictício/vazio."""
    if not vat or vat_ficticio(vat):
        return ""
    v = re.sub(r"[^A-Z0-9]", "", vat.upper())
    return v[2:] if len(v) > 2 and v[:2].isalpha() and not v[2].isalpha() else v


def _nif_igual(a, b):
    """Igual com tolerância ao prefixo do país (ESB12345678 ≈ B12345678)."""
    curto, longo = sorted((a, b), key=len)
    return a == b or (len(longo) == len(curto) + 2 and longo[:2].isalpha() and longo[2:] == curto)


def _num(value, digits=2):
    """Número no formato português, seja qual for a língua do utilizador: 12.345,67"""
    value = round(value or 0.0, digits)
    if value == 0:
        value = 0.0  # evita "-0,00"
    s = f"{value:,.{digits}f}"
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _eur(value, digits=2):
    return f"{_num(value, digits)}\N{NO-BREAK SPACE}€"


def _casas(value, minimo=2, maximo=4):
    """Casas decimais necessárias (entre minimo e maximo)."""
    for d in range(minimo, maximo):
        if abs(round(value or 0.0, d) - round(value or 0.0, maximo)) < 1e-9:
            return d
    return maximo


def _data(dt):
    return dt.strftime("%d/%m/%Y")


class CrmLead(models.Model):
    _inherit = "crm.lead"

    def action_historico_primavera(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "mirazeite_crm_historico_primavera.historico",
            "name": _("Histórico Primavera"),
            "target": "new",
            "params": {"lead_id": self.id},
            "context": {"dialog_size": "extra-large"},
        }

    def get_historico_primavera(self):
        """Faturas e notas de crédito do cliente no Primavera (só leitura, nada gravado)."""
        self.ensure_one()
        # Permissões existentes: tem de poder abrir esta oportunidade e ver faturas.
        self.check_access("read")
        if not self.env["account.move"].has_access("read"):
            raise AccessError(_("Não tem permissão para ver faturas."))

        if not self.partner_id:
            return {"error": _("Esta oportunidade não tem cliente.")}
        # A ficha da oportunidade, ou a empresa a que pertence (contactos de pessoas).
        partner = self.partner_id
        if not partner.primavera_customer_code:
            partner = partner.commercial_partner_id
        codigo = (partner.primavera_customer_code or "").strip()
        if not codigo:
            return {"error": _("O cliente %s não tem código de cliente Primavera.") % partner.display_name}

        hoje = fields.Date.context_today(self)
        anos = [hoje.year, hoje.year - 1]
        inicio, fim = date(hoje.year - 1, 1, 1), hoje + timedelta(days=1)

        conn = self.env["primavera.connection"].sudo().search([("active", "=", True)], limit=1)
        sql = conn._sql_connection() if conn else None
        if not sql:
            return {"error": _("Sem ligação ao Primavera neste momento. Tente mais tarde.")}
        try:
            with sql.cursor(as_dict=True) as cur:
                cur.execute(SQL_CLIENTE, (codigo,))
                cliente = cur.fetchone()
                if not cliente:
                    return {"error": _("O código %s não existe nos clientes do Primavera.") % codigo}
                nif_odoo, nif_prim = _nif(partner.vat), _nif(cliente["NumContrib"])
                if nif_odoo and nif_prim and not _nif_igual(nif_odoo, nif_prim):
                    return {"error": _(
                        "O código %(c)s não corresponde a este cliente: NIF no Odoo %(o)s, "
                        "NIF no Primavera %(p)s (%(n)s).",
                        c=codigo, o=partner.vat, p=cliente["NumContrib"], n=cliente["Nome"])}
                cur.execute(SQL_DOCUMENTOS, (codigo, inicio, fim))
                cabecs = cur.fetchall()
                cur.execute(SQL_LINHAS, (codigo, inicio, fim))
                linhas = cur.fetchall()
        except Exception:
            _logger.exception("Histórico Primavera: erro a ler o cliente %s", codigo)
            return {"error": _("Não foi possível ler o Primavera neste momento. Tente mais tarde.")}
        finally:
            sql.close()

        linhas_por_doc, vistas = {}, set()
        for ln in linhas:
            if ln["Id"] in vistas:
                continue
            vistas.add(ln["Id"])
            linhas_por_doc.setdefault(str(ln["IdCabecDoc"]), []).append(ln)

        grupos = {a: {"year": a, "invoices": [], "t": 0.0, "tf": 0.0, "tnc": 0.0, "nf": 0, "nnc": 0} for a in anos}
        docs_vistos = set()
        for c in cabecs:
            doc_id = str(c["Id"])
            ano = c["Data"].year
            if doc_id in docs_vistos or ano not in grupos:
                continue
            docs_vistos.add(doc_id)
            tipo = c["TipoDoc"].strip()
            credito = tipo in TIPOS_NOTA_CREDITO
            liquido = (c["TotalMerc"] or 0.0) - (c["TotalDesc"] or 0.0) + (c["TotalOutros"] or 0.0)
            if credito:
                liquido = -abs(liquido)  # já vem negativo do Primavera; garantido
            lines, soma = [], 0.0
            for ln in linhas_por_doc.get(doc_id, []):
                valor = ln["PrecoLiquido"] or 0.0
                if credito:
                    valor = -abs(valor)
                soma += valor
                lines.append(self._hp_linha(ln, c, credito, valor))
            g = grupos[ano]
            g["invoices"].append({
                "id": doc_id,
                "name": f"{tipo} {c['Serie'].strip()}/{c['NumDoc']}",
                "is_credit": credito,
                "date": _data(c["Data"]),
                "amount": _eur(liquido),
                "lines": lines,
                "lines_total": _eur(soma),
                "lines_ok": abs(soma - liquido) < 0.01
                and abs(abs((c["TotalDocumento"] or 0.0) - (c["TotalIva"] or 0.0)) - abs(liquido)) < 0.01,
                "currency_note": (c["Moeda"] or "EUR").strip() != "EUR" and (c["Moeda"] or "").strip(),
            })
            g["t"] += liquido
            if credito:
                g["tnc"] += liquido
                g["nnc"] += 1
            else:
                g["tf"] += liquido
                g["nf"] += 1

        years = []
        for a in anos:
            g = grupos.pop(a)
            years.append({
                "year": a,
                "invoices": g["invoices"],
                "count": len(g["invoices"]),
                "count_invoices": g["nf"],
                "count_credits": g["nnc"],
                "total": _eur(g["t"]),
                "total_invoices": _eur(g["tf"]),
                "total_credits": _eur(g["tnc"]),
            })
        return {
            "customer": {
                "code": cliente["Cliente"],
                "name": cliente["Nome"],
                "vat": cliente["NumContrib"] or "",
                "nif_validated": bool(nif_odoo and nif_prim),
                "archived": bool(cliente["ClienteAnulado"]),
            },
            "period": f"{_data(inicio)} a {_data(hoje)}",
            "doc_types": ", ".join(TIPOS_FATURA),
            "credit_types": ", ".join(TIPOS_NOTA_CREDITO),
            "years": years,
            "count": len(docs_vistos),
        }

    def _hp_linha(self, ln, cabec, credito, valor):
        pu = abs(ln["PrecUnit"] or 0.0)  # preço positivo; o sinal vai na quantidade e no valor
        qtd = ln["Quantidade"] or 0.0
        if credito:
            qtd = -abs(qtd)
        partes = [f"{_num(d)} %" for d in (ln["Desconto1"], ln["Desconto2"], ln["Desconto3"]) if d]
        if ln["TotalDC"] and cabec["DescEntidade"]:
            partes.append(_("%s %% cliente") % _num(cabec["DescEntidade"]))
        if ln["TotalDF"] and cabec["DescPag"]:
            partes.append(_("%s %% financeiro") % _num(cabec["DescPag"]))
        desc_valor = abs(ln["TotalDA"] or 0.0) + abs(ln["TotalDC"] or 0.0) + abs(ln["TotalDF"] or 0.0)
        return {
            "id": str(ln["Id"]),
            "code": ln["Artigo"] or "",
            "description": ln["Descricao"] or "",
            "quantity": _num(qtd, _casas(qtd, 0, 3)),
            "uom": ln["Unidade"] or "",
            "price_unit": _eur(pu, _casas(pu)),
            "discount": " + ".join(partes),
            "discount_amount": _eur(desc_valor) if desc_valor else "",
            "amount": _eur(valor),
            "negative": valor < 0,
        }
