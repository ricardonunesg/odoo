import logging
import re
from datetime import date, timedelta

from odoo import _, fields, models
from odoo.exceptions import AccessError
from odoo.tools.misc import format_date, formatLang

from odoo.addons.primavera_connector.models.primavera_connection import vat_ficticio

_logger = logging.getLogger(__name__)

# Faturas de venda (DocumentosVenda.TipoDocumento = 4). Ficam de fora notas de
# crédito/débito (NC*, ND), estornos (DFRT), adiantamentos (FAA, FAAT),
# pró-formas (FP) e faturas de imobilizado (FM).
TIPOS_FATURA = ("FA", "FAT", "FR", "FRT", "FS")
# Linhas de comentário (sem valores) não são mostradas.
TIPO_LINHA_COMENTARIO = "60"

# Só SELECT. Valores sem IVA validados em 2482 faturas 2025–2026 (10/11/2026):
#   TotalMerc − TotalDesc + TotalOutros = TotalDocumento − TotalIva = Σ PrecoLiquido
# PrecUnit × Quantidade = TotalIliquido → PrecUnit é o preço ANTES dos descontos;
# PrecoLiquido é o valor da linha já com o desconto de linha (TotalDA) e a parte
# do desconto global do cliente (TotalDC) e financeiro (TotalDF).
_WHERE = (
    "c.TipoEntidade = 'C' AND c.Entidade = %s "
    f"AND c.TipoDoc IN ({', '.join(repr(t) for t in TIPOS_FATURA)}) "
    "AND ISNULL(s.Anulado, 0) = 0 AND c.Data >= %s AND c.Data < %s"
)
SQL_FATURAS = (
    "SELECT c.Id, c.TipoDoc, c.Serie, c.NumDoc, c.Data, c.Moeda, "
    "c.TotalMerc, c.TotalDesc, c.TotalOutros, c.TotalIva, c.TotalDocumento, "
    "c.DescEntidade, c.DescPag "
    "FROM CabecDoc c JOIN CabecDocStatus s ON s.IdCabecDoc = c.Id "
    f"WHERE {_WHERE} ORDER BY c.Data DESC, c.NumDoc DESC"
)
SQL_LINHAS = (
    "SELECT l.IdCabecDoc, l.Id, l.NumLinha, l.Artigo, l.Descricao, l.Quantidade, l.Unidade, "
    "l.PrecUnit, l.Desconto1, l.Desconto2, l.Desconto3, l.TotalIliquido, "
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

    # ------------------------------------------------------------------
    def _hp_num(self, value, digits=2):
        return formatLang(self.env, value or 0.0, digits=digits)

    def _hp_eur(self, value, digits=2):
        return f"{self._hp_num(value, digits)}\N{NO-BREAK SPACE}€"

    @staticmethod
    def _hp_digits(value, minimum=2, maximum=4):
        """Casas decimais necessárias (entre minimum e maximum)."""
        for d in range(minimum, maximum):
            if abs(round(value or 0.0, d) - round(value or 0.0, maximum)) < 1e-9:
                return d
        return maximum

    def get_historico_primavera(self):
        """Faturas do cliente da oportunidade no Primavera (só leitura, nada gravado)."""
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
                cur.execute(SQL_FATURAS, (codigo, inicio, fim))
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

        grupos = {a: {"year": a, "invoices": [], "total": 0.0} for a in anos}
        docs_vistos = set()
        for c in cabecs:
            doc_id = str(c["Id"])
            ano = c["Data"].year
            if doc_id in docs_vistos or ano not in grupos:
                continue
            docs_vistos.add(doc_id)
            liquido = (c["TotalMerc"] or 0.0) - (c["TotalDesc"] or 0.0) + (c["TotalOutros"] or 0.0)
            lines, soma = [], 0.0
            for ln in linhas_por_doc.get(doc_id, []):
                soma += ln["PrecoLiquido"] or 0.0
                lines.append(self._hp_linha(ln, c))
            grupos[ano]["invoices"].append({
                "id": doc_id,
                "name": f"{c['TipoDoc'].strip()} {c['Serie'].strip()}/{c['NumDoc']}",
                "date": format_date(self.env, c["Data"].date()),
                "amount": self._hp_eur(liquido),
                "lines": lines,
                "lines_total": self._hp_eur(soma),
                "lines_ok": abs(soma - liquido) < 0.01
                and abs((c["TotalDocumento"] or 0.0) - (c["TotalIva"] or 0.0) - liquido) < 0.01,
                "currency_note": (c["Moeda"] or "EUR").strip() != "EUR" and (c["Moeda"] or "").strip(),
            })
            grupos[ano]["total"] += liquido

        years = []
        for a in anos:
            g = grupos[a]
            g["count"] = len(g["invoices"])
            g["total"] = self._hp_eur(g["total"])
            years.append(g)
        return {
            "customer": {
                "code": cliente["Cliente"],
                "name": cliente["Nome"],
                "vat": cliente["NumContrib"] or "",
                "nif_validated": bool(nif_odoo and nif_prim),
                "archived": bool(cliente["ClienteAnulado"]),
            },
            "period": _("%(d1)s a %(d2)s", d1=format_date(self.env, inicio), d2=format_date(self.env, hoje)),
            "doc_types": ", ".join(TIPOS_FATURA),
            "years": years,
            "count": len(docs_vistos),
        }

    def _hp_linha(self, ln, cabec):
        pu = ln["PrecUnit"] or 0.0
        qtd = ln["Quantidade"] or 0.0
        partes = [f"{self._hp_num(d)} %" for d in (ln["Desconto1"], ln["Desconto2"], ln["Desconto3"]) if d]
        if ln["TotalDC"] and cabec["DescEntidade"]:
            partes.append(_("%s %% cliente") % self._hp_num(cabec["DescEntidade"]))
        if ln["TotalDF"] and cabec["DescPag"]:
            partes.append(_("%s %% financeiro") % self._hp_num(cabec["DescPag"]))
        desc_valor = (ln["TotalDA"] or 0.0) + (ln["TotalDC"] or 0.0) + (ln["TotalDF"] or 0.0)
        return {
            "id": str(ln["Id"]),
            "code": ln["Artigo"] or "",
            "description": ln["Descricao"] or "",
            "quantity": self._hp_num(qtd, self._hp_digits(qtd, 0, 3)),
            "uom": ln["Unidade"] or "",
            "price_unit": self._hp_eur(pu, self._hp_digits(pu)),
            "discount": " + ".join(partes),
            "discount_amount": self._hp_eur(desc_valor) if desc_valor else "",
            "amount": self._hp_eur(ln["PrecoLiquido"]),
        }
