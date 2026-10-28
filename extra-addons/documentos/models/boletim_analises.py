import re as _re
from odoo import api, fields, models

# Mapeamento prefixo de lote → tipo de produto (partilhado com CertificadoSalubridade)
_LOTE_TIPO = {
    'LAV':  ('Azeite Virgem Extra',        'Extra Virgin Olive Oil'),
    'LAC':  ('Azeite',                     'Olive Oil'),
    'LTP':  ('Tempero Alimentar',          'Food Seasoning'),
    'LTPT': ('Tempero Alimentar',          'Food Seasoning'),
    'LOG':  ('Azeite de Bagaço (Pomace)',  'Pomace Olive Oil'),
    'LOGT': ('Azeite de Bagaço (Pomace)',  'Pomace Olive Oil'),
}


def _prefixo_lote(lote_str):
    if not lote_str:
        return 'OUTRO'
    m = _re.match(r'^([A-Za-z]{2,4})', lote_str.strip())
    return m.group(1).upper() if m else 'OUTRO'


class BoletimAnalisesTemplate(models.Model):
    _name = "boletim.analises.template"
    _description = "Modelo de Boletim de Análises"
    _rec_name = "name"
    _order = "sequence, name"

    name     = fields.Char("Nome", required=True)
    sequence = fields.Integer(default=10)
    active   = fields.Boolean(default=True)
    default_morada_id = fields.Many2one("documento.morada", "Morada padrão")

    # ── Bloco Importador ────────────────────────────────────────────────────
    show_importador     = fields.Boolean("Importador",             default=True)
    show_morada_cliente = fields.Boolean("Morada do importador",   default=True)
    show_cnpj_cliente   = fields.Boolean("CNPJ do importador",     default=True)
    show_distribuidor   = fields.Boolean("Distribuidor",           default=False)
    # ── Bloco Orderer ───────────────────────────────────────────────────────
    show_orderer        = fields.Boolean("Orderer",                default=False)
    show_morada_orderer = fields.Boolean("Morada do Orderer",      default=False)
    show_cnpj_orderer   = fields.Boolean("CNPJ do Orderer",        default=False)
    # ── Datas ────────────────────────────────────────────────────────────────
    show_recepcao           = fields.Boolean("Receção",              default=True)
    show_inicio_analises    = fields.Boolean("Início das análises",  default=True)
    show_fim_analises       = fields.Boolean("Fim das análises",     default=True)
    # ── Produto / Amostra ────────────────────────────────────────────────────
    show_amostra        = fields.Boolean("Amostra",                default=True)
    show_tipo_analise   = fields.Boolean("Tipo",                   default=True)
    show_safra          = fields.Boolean("Safra",                  default=True)
    show_procedencia    = fields.Boolean("Procedência",            default=True)
    show_lote           = fields.Boolean("Lote",                   default=True)
    show_acidez_max     = fields.Boolean("Acidez máx.",            default=True)
    show_contentor      = fields.Boolean("Contentor n.º",         default=True)
    # ── Embalagem / Pesos ────────────────────────────────────────────────────
    show_marca_embalagem    = fields.Boolean("Marca e Embalagem",  default=True)
    show_peso_liquido       = fields.Boolean("Peso Líquido (kg)",  default=True)
    show_data_envasado      = fields.Boolean("Envasado (data)",    default=True)
    show_peso_bruto         = fields.Boolean("Peso Bruto (kg)",    default=True)
    show_data_validade      = fields.Boolean("Data de Validade",   default=True)
    show_total_caixas       = fields.Boolean("Nº Volumes",         default=True)
    # ── Tabela de análises e outros ──────────────────────────────────────────
    show_product_code       = fields.Boolean("Código de artigo",   default=False)
    show_description        = fields.Boolean("Descrição",          default=True)
    show_quantidade         = fields.Boolean("Quantidade",         default=True)
    show_unidade            = fields.Boolean("Unidade",            default=True)
    show_total_peso_liquido = fields.Boolean("Total peso líquido", default=True)
    show_total_peso_bruto   = fields.Boolean("Total peso bruto",   default=True)
    show_observacoes        = fields.Boolean("Observações",        default=False)
    show_fatura             = fields.Boolean("Fatura n.º",         default=True)
    show_data               = fields.Boolean("Data",               default=True)
    in_english              = fields.Boolean("Em Inglês",          default=False)


class BoletimAnalises(models.Model):
    _name = "boletim.analises"
    _description = "Boletim de Análises"
    _rec_name = "name"
    _order = "id desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char("Referência", readonly=True, copy=False, default="Novo")
    state = fields.Selection(
        [("draft", "Rascunho"), ("confirmed", "Confirmado"), ("cancelled", "Cancelado")],
        default="draft", required=True, string="Estado",
    )
    company_id = fields.Many2one(
        "res.company", "Empresa",
        default=lambda self: self.env.company,
        required=True, readonly=True,
    )
    template_id = fields.Many2one("boletim.analises.template", "Modelo", required=True)
    date        = fields.Date("Data", default=fields.Date.today)
    fatura_id   = fields.Many2one(
        "account.move", "Fatura origem",
        domain=[("primavera_ref", "!=", False), ("move_type", "=", "out_invoice")],
    )
    fatura_ref     = fields.Char("Fatura")

    # ── Importador ──────────────────────────────────────────────────────────
    importador     = fields.Char("Importador")
    morada_cliente = fields.Text("Morada do importador")
    cnpj_cliente   = fields.Char("CNPJ do importador")
    distribuidor   = fields.Char("Distribuidor")

    # ── Orderer ─────────────────────────────────────────────────────────────
    orderer        = fields.Char("Orderer")
    morada_orderer = fields.Text("Morada do Orderer")
    cnpj_orderer   = fields.Char("CNPJ do Orderer")

    # ── Datas (texto livre) ─────────────────────────────────────────────────
    recepcao            = fields.Char("Receção")
    data_inicio_analises = fields.Char("Início das análises")
    data_fim_analises   = fields.Char("Fim das análises")

    # ── Produto / Amostra ───────────────────────────────────────────────────
    amostra          = fields.Char("Amostra")
    tipo_analise     = fields.Char("Tipo")
    safra            = fields.Char("Safra")
    procedencia      = fields.Char("Procedência")
    lotes_descricao  = fields.Char("Lote(s)")
    acidez_max       = fields.Char("Acidez máx.")
    contentor        = fields.Char("Contentor n.º")

    # ── Embalagem / Pesos ───────────────────────────────────────────────────
    marca_embalagem  = fields.Char("Marca e Embalagem")
    data_envasado    = fields.Char("Envasado (data)")
    data_validade    = fields.Char("Data de Validade")

    # ── Outros ─────────────────────────────────────────────────────────────
    ref_cliente    = fields.Char("V/Ref Cliente")
    destino        = fields.Char("Destino")
    observacoes    = fields.Text("Observações")

    morada_id     = fields.Many2one(
        "documento.morada", "Morada",
        default=lambda self: self.env.company.default_report_morada_id,
    )
    morada_street  = fields.Char(related="morada_id.street",  string="Rua",         readonly=True)
    morada_street2 = fields.Char(related="morada_id.street2", string="Rua 2",       readonly=True)
    morada_zip     = fields.Char(related="morada_id.zip",     string="Cód. Postal", readonly=True)
    morada_city    = fields.Char(related="morada_id.city",    string="Localidade",  readonly=True)
    morada_phone   = fields.Char(related="morada_id.phone",   string="Telefone",    readonly=True)
    morada_email   = fields.Char(related="morada_id.email",   string="Email",       readonly=True)
    morada_vat     = fields.Char(related="morada_id.vat",     string="Contribuinte",readonly=True)
    morada_sede    = fields.Text(related="morada_id.sede",    string="Sede",        readonly=True)

    line_ids = fields.One2many("boletim.analises.linha", "documento_id", "Linhas")
    resultado_ids = fields.One2many("boletim.analises.resultado", "boletim_id", "Resultados de Análise")

    total_peso_liquido = fields.Float("Total P. Líq. (kg)", compute="_compute_totals", store=True, digits=(16, 3))
    total_peso_bruto   = fields.Float("Total P. Bruto (kg)", compute="_compute_totals", store=True, digits=(16, 3))
    total_caixas       = fields.Integer("Nº Volumes",        compute="_compute_totals", store=True)

    # Visibilidade via template
    show_importador         = fields.Boolean(related="template_id.show_importador")
    show_morada_cliente     = fields.Boolean(related="template_id.show_morada_cliente")
    show_cnpj_cliente       = fields.Boolean(related="template_id.show_cnpj_cliente")
    show_distribuidor       = fields.Boolean(related="template_id.show_distribuidor")
    show_orderer            = fields.Boolean(related="template_id.show_orderer")
    show_morada_orderer     = fields.Boolean(related="template_id.show_morada_orderer")
    show_cnpj_orderer       = fields.Boolean(related="template_id.show_cnpj_orderer")
    show_recepcao           = fields.Boolean(related="template_id.show_recepcao")
    show_inicio_analises    = fields.Boolean(related="template_id.show_inicio_analises")
    show_fim_analises       = fields.Boolean(related="template_id.show_fim_analises")
    show_amostra            = fields.Boolean(related="template_id.show_amostra")
    show_tipo_analise       = fields.Boolean(related="template_id.show_tipo_analise")
    show_safra              = fields.Boolean(related="template_id.show_safra")
    show_procedencia        = fields.Boolean(related="template_id.show_procedencia")
    show_lote               = fields.Boolean(related="template_id.show_lote")
    show_acidez_max         = fields.Boolean(related="template_id.show_acidez_max")
    show_contentor          = fields.Boolean(related="template_id.show_contentor")
    show_marca_embalagem    = fields.Boolean(related="template_id.show_marca_embalagem")
    show_peso_liquido       = fields.Boolean(related="template_id.show_peso_liquido")
    show_data_envasado      = fields.Boolean(related="template_id.show_data_envasado")
    show_peso_bruto         = fields.Boolean(related="template_id.show_peso_bruto")
    show_data_validade      = fields.Boolean(related="template_id.show_data_validade")
    show_total_caixas       = fields.Boolean(related="template_id.show_total_caixas")
    show_product_code       = fields.Boolean(related="template_id.show_product_code")
    show_description        = fields.Boolean(related="template_id.show_description")
    show_quantidade         = fields.Boolean(related="template_id.show_quantidade")
    show_unidade            = fields.Boolean(related="template_id.show_unidade")
    show_total_peso_liquido = fields.Boolean(related="template_id.show_total_peso_liquido")
    show_total_peso_bruto   = fields.Boolean(related="template_id.show_total_peso_bruto")
    show_observacoes        = fields.Boolean(related="template_id.show_observacoes")
    show_fatura             = fields.Boolean(related="template_id.show_fatura")
    show_ref_cliente        = fields.Boolean(default=False, store=False, compute=lambda self: False)
    show_destino            = fields.Boolean(default=False, store=False, compute=lambda self: False)
    show_data               = fields.Boolean(related="template_id.show_data")
    in_english              = fields.Boolean(related="template_id.in_english")


    @api.depends("line_ids.pliquidot", "line_ids.pbrutot", "line_ids.quantidade")
    def _compute_totals(self):
        for rec in self:
            rec.total_peso_liquido = sum(rec.line_ids.mapped("pliquidot"))
            rec.total_peso_bruto   = sum(rec.line_ids.mapped("pbrutot"))
            rec.total_caixas       = sum(int(l.quantidade or 0) for l in rec.line_ids)

    @api.onchange("template_id")
    def _onchange_template(self):
        if self.template_id and self.template_id.default_morada_id:
            self.morada_id = self.template_id.default_morada_id
        elif self.company_id.default_report_morada_id:
            self.morada_id = self.company_id.default_report_morada_id

    @api.onchange("fatura_id")
    def _onchange_fatura(self):
        fatura = self.fatura_id
        if not fatura:
            return
        self.fatura_ref   = fatura.primavera_ref or fatura.name
        self.importador   = fatura.importador or fatura.partner_id.name or self.importador
        self.distribuidor = fatura.distribuidor or self.distribuidor
        self.contentor    = fatura.contentor or self.contentor
        self.ref_cliente  = fatura.ref_cliente or self.ref_cliente
        self.destino = (
            fatura.pais_destino_id.name if fatura.pais_destino_id else fatura.destino or self.destino
        )
        partner = fatura.partner_id
        if partner:
            parts = [p for p in [partner.street, partner.street2, partner.zip, partner.city, partner.country_id.name] if p]
            self.morada_cliente = ", ".join(parts)

    def action_load_fatura_lines(self):
        """Agrupa linhas da fatura por tipo de produto e cria 1 boletim por tipo."""
        self.ensure_one()
        if not self.fatura_id:
            return

        fatura  = self.fatura_id
        partner = fatura.partner_id

        # Dados comuns de cabeçalho
        cabecalho = {
            'fatura_ref':     fatura.primavera_ref or fatura.name,
            'importador':     fatura.importador or partner.name or self.importador,
            'distribuidor':   fatura.distribuidor or self.distribuidor,
            'contentor':      fatura.contentor or self.contentor,
            'destino':        (fatura.pais_destino_id.name if fatura.pais_destino_id
                               else fatura.destino or self.destino),
            'fatura_id':      fatura.id,
        }
        if partner:
            parts = [p for p in [partner.street, partner.street2,
                                  partner.zip, partner.city,
                                  partner.country_id.name] if p]
            cabecalho['morada_cliente'] = '\n'.join(parts)
            if partner.vat:
                cabecalho['cnpj_cliente'] = partner.vat

        # Linhas de produto (excluir paletes)
        inv_lines = fatura.invoice_line_ids.filtered(
            lambda l: l.display_type == 'product'
            and l.product_id
            and l.product_id.default_code
            and not (l.product_id.default_code or '').upper().startswith('PAL')
        )
        if not inv_lines:
            return {"type": "ir.actions.client", "tag": "reload"}

        liquido = inv_lines._peso_liquido_unit()

        # Agrupar por prefixo de lote — só prefixos reconhecidos
        grupos = {}
        for l in inv_lines:
            lote = l.lote or ''
            if lote.startswith('<') and lote.endswith('>'):
                lote = ''
            pref = _prefixo_lote(lote)
            if pref not in _LOTE_TIPO:
                continue
            grupos.setdefault(pref, []).append(l)

        if not grupos:
            return {"type": "ir.actions.client", "tag": "reload"}

        prefixos = sorted(grupos.keys())

        def _linhas_vals(doc_id, linhas):
            vals = []
            for i, l in enumerate(linhas):
                product = l.product_id
                lote = l.lote or ''
                if lote.startswith('<') and lote.endswith('>'):
                    lote = ''
                vals.append({
                    'documento_id':  doc_id,
                    'sequence':      (i + 1) * 10,
                    'product_code':  product.default_code,
                    'description':   l.name or '',
                    'lote':          lote,
                    'data_validade': l.data_validade,
                    'quantidade':    l.caixas or int(l.quantity),
                    'unidade':       product.uom_id.name or '',
                    'peso_liquido':  liquido[l.id],
                    'peso_bruto':    l.peso_bruto or product.weight,
                })
            return vals

        todos_ids = [self.id]

        def _preencher_extras(doc, prefixo, linhas):
            """Popula campos derivados das linhas: lotes, totais, datas."""
            lotes = []
            total_cx = 0
            total_pl = 0.0
            total_pb = 0.0
            first_val = None
            first_fab = None
            for l in linhas:
                lt = l.lote or ''
                if lt.startswith('<') and lt.endswith('>'):
                    lt = ''
                if lt and lt not in lotes:
                    lotes.append(lt)
                total_cx += l.caixas or int(l.quantity)
                total_pl += (l.caixas or int(l.quantity)) * liquido[l.id]
                total_pb += (l.caixas or int(l.quantity)) * (l.peso_bruto or l.product_id.weight or 0)
                if first_val is None:
                    first_val = l.data_validade or l.product_id.x_data_validade
                if first_fab is None:
                    first_fab = l.product_id.x_data_fabricacao
            extras = {
                'lotes_descricao':   ', '.join(lotes),
                'total_caixas':      total_cx,
                'total_peso_liquido': total_pl,
                'total_peso_bruto':   total_pb,
            }
            if first_val:
                extras['data_validade'] = f"{first_val.month:02d}/{first_val.year}"
            if first_fab:
                extras['data_envasado'] = f"{first_fab.month:02d}/{first_fab.year}"
            doc.write(extras)

        # Gerar número para o boletim actual se ainda for 'Novo'
        if self.name == 'Novo':
            self.name = (
                self.env['ir.sequence'].next_by_code_sem_repetir('boletim.analises', 'boletim.analises') or 'Novo'
            )

        # Preencher boletim actual com 1º grupo
        self.write(cabecalho)
        self.line_ids.unlink()
        v = _linhas_vals(self.id, grupos[prefixos[0]])
        if v:
            self.env['boletim.analises.linha'].create(v)
        _preencher_extras(self, prefixos[0], grupos[prefixos[0]])
        if not self.resultado_ids:
            self._popular_resultados_padrao()

        # Criar novos boletins para prefixos adicionais
        for prefixo in prefixos[1:]:
            seq = self.env['ir.sequence'].next_by_code_sem_repetir('boletim.analises', 'boletim.analises') or 'Novo'
            novo = self.create({
                'name':        seq,
                'template_id': self.template_id.id,
                'date':        self.date,
                'fatura_id':   fatura.id,
                'morada_id':   self.morada_id.id if self.morada_id else False,
                **cabecalho,
            })
            v = _linhas_vals(novo.id, grupos[prefixo])
            if v:
                self.env['boletim.analises.linha'].create(v)
            _preencher_extras(novo, prefixo, grupos[prefixo])
            if not novo.resultado_ids:
                novo._popular_resultados_padrao()
            todos_ids.append(novo.id)

        if len(todos_ids) == 1:
            return {"type": "ir.actions.client", "tag": "reload"}

        return {
            'type':      'ir.actions.act_window',
            'name':      f'Boletins — {fatura.primavera_ref or fatura.name}',
            'res_model': 'boletim.analises',
            'view_mode': 'list,form',
            'domain':    [('id', 'in', todos_ids)],
            'target':    'current',
        }

    def _popular_resultados_padrao(self):
        """Cria as linhas de resultado padrão se ainda não existirem."""
        Resultado = self.env["boletim.analises.resultado"].sudo()
        for seq, rtype, analise, metodo, limites, resultado in _RESULTADOS_PADRAO:
            Resultado.create({
                "boletim_id": self.id, "sequence": seq, "row_type": rtype,
                "analise": analise, "metodo": metodo,
                "limites_legais": limites, "resultado": resultado,
            })

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if not rec.resultado_ids:
                rec._popular_resultados_padrao()
        return records

    def action_confirm(self):
        for rec in self:
            if rec.name == "Novo":
                rec.name = self.env["ir.sequence"].next_by_code_sem_repetir("boletim.analises", "boletim.analises") or "Novo"
            rec.state = "confirmed"

    def action_reset_draft(self):
        self.write({"state": "draft"})

    def action_cancel(self):
        self.write({"state": "cancelled"})

    def action_print_pdf(self):
        for rec in self:
            if rec.name == "Novo":
                rec.name = self.env["ir.sequence"].next_by_code_sem_repetir("boletim.analises", "boletim.analises") or "Novo"
        return self.env.ref("documentos.action_report_boletim_analises").report_action(self)


class BoletimAnalisesLinha(models.Model):
    _name = "boletim.analises.linha"
    _description = "Linha de Boletim de Análises"
    _order = "sequence, id"

    documento_id  = fields.Many2one("boletim.analises", required=True, ondelete="cascade", index=True)
    sequence      = fields.Integer(default=10)
    product_code  = fields.Char("Cód. Artigo")
    description   = fields.Char("Descrição")
    lote          = fields.Char("Lote")
    data_validade = fields.Date("Validade")
    quantidade    = fields.Float("Qnt", digits=(16, 2))
    unidade       = fields.Char("Uni")
    peso_liquido  = fields.Float("P. Líq. Unit. (kg)", digits="Stock Weight")
    peso_bruto    = fields.Float("P. Bruto Unit. (kg)", digits="Stock Weight")
    pliquidot     = fields.Float("P. Líq. Total (kg)", compute="_compute_totais", store=True, digits=(16, 3))
    pbrutot       = fields.Float("P. Bruto Total (kg)", compute="_compute_totais", store=True, digits=(16, 3))
    observacoes   = fields.Char("Obs.")

    @api.depends("quantidade", "peso_liquido", "peso_bruto")
    def _compute_totais(self):
        for line in self:
            line.pliquidot = line.quantidade * line.peso_liquido
            line.pbrutot   = line.quantidade * line.peso_bruto


# ── Dados padrão para resultados analíticos (Extra Virgem) ────────────────────
# seq, row_type, analise, metodo, limites_legais, resultado
_RESULTADOS_PADRAO = [
    (10,'normal','Acidez Livre (% ácido oleico)','Titulação','≤ 0,8','0,18'),
    (20,'normal','Extinção específica no ultravioleta    K270','Espectrofotometria','≤0,22','0,15'),
    (25,'sub','K232','','≤2,50','1,78'),
    (27,'sub','Delta K','','≤0,01','-0,003'),
    (30,'normal','Índice de peróxidos (mEq/Kg)','Titulação','≤ 20,0','9,0'),
    (40,'normal','Estigmastadienos (mg/kg)','Cromatografia Gasosa','≤ 0,15','0,02'),
    (50,'normal','Ceras (mg/Kg)','Cromatografia Gasosa','≤ 250','78'),
    (60,'normal','Diferença do ECN 42','Cromatografia Líquida','≤ 0,2','0,00'),
    (70,'header','Composição de ácidos graxos:','Cromatografia Gasosa','LIMITES LEGAIS','RESULTADOS'),
    (80,'normal','18:1t (%) – Transoleico','','≤ 0,05','0,02'),
    (90,'normal','18:2t + 18:3t (%) – Translinoleico + Translinolénico','','≤ 0,05','0,03'),
    (100,'normal','C14:0 (%) – Mirístico','','≤ 0,05','0,01'),
    (110,'normal','C16:0 (%) – Palmítico','','7,5 - 20,0','11,56'),
    (120,'normal','C16:1 (%) – Palmitoleico','','0,3 - 3,5','0,77'),
    (130,'normal','C17:0 (%) – n-Heptadecanoico','','≤ 0,3','0,06'),
    (140,'normal','C17:1 (%) – 9-Heptadecanoico','','≤ 0,3','0,11'),
    (150,'normal','C18:0 (%) – Esteárico','','0,5 - 5,0','3,11'),
    (160,'normal','C18:1 (%) – Oleico','','55,0 - 83,0','72,86'),
    (170,'normal','C18:2 (%) – Linoleico','','3,5 - 21,0','9,95'),
    (180,'normal','C18:3 (%) – Linolénico','','≤ 1,0','0,74'),
    (190,'normal','C20:0 (%) – Aráquico','','≤ 0,6','0,40'),
    (200,'normal','C20:1 (%) – Gadoleico','','≤ 0,4','0,24'),
    (210,'normal','C22:0 (%) – Beénico','','≤ 0,2','0,10'),
    (220,'normal','C24:0 (%) – Lignocérico','','≤ 0,2','0,04'),
    (230,'header','Composição de esteróis:','Cromatografia Gasosa','LIMITES LEGAIS','RESULTADOS'),
    (240,'normal','Colesterol (%)','','≤ 0,5','0,1'),
    (250,'normal','Campesterol (%)','','≤ 4,0','2,3'),
    (260,'normal','Estigmasterol (%)','','< Campesterol result','1,2'),
    (270,'normal','Brassicasterol (%)','','≤ 0,1','0,01'),
    (280,'normal','Beta-sitosterol + delta-5,23-estigmastadienol + Clerosterol + beta-Sitotanol + delta-5-Avenasterol + Delta-5,24-Estigmastadienol','','≥ 93,0','94,3'),
    (290,'normal','Δ-7-estigmastenol (%)','','≤ 0,5','0,3'),
    (300,'normal','Eritrodiol e Uvaol (%)','','≤ 4,5','2,2'),
    (310,'normal','Esteróis Totais (mg/kg)','','≥ 1000','1581'),
    (320,'section','APENDICE IV','','',''),
    (330,'normal','Ésteres Metílicos de Ácidos Graxos (EMAG) e Ésteres Etílicos de Ácidos Graxos (EEAG)','Cromatografia Gasosa','∑EMAG+∑EEAG ≤ 75mg/kg ou 75mg<∑EMAG+EEAG≤150mg/kg e (EEAG/EMAG ≤1,5)','30'),
    (340,'normal','Índice de Refração (Raia D a 20ºC)','Refratómetro','1,4677 – 1,4705','1,4681'),
    (350,'normal','Índice de Saponificação (mg KOH/g)','Titulação','184 – 196','190'),
    (360,'normal','Umidade e material volátil (%)','Gravimetria','≤ 0,2','0,05'),
    (370,'normal','Material Insaponificável (g/kg)','Extração e Gravimetria','≤15,0','12,2'),
    (380,'normal','Impurezas Insolúveis (%)','Gravimetria','≤0,1','0,03'),
    (390,'normal','Índice de Iodo (Wijs)','Titulação','75 – 94','87'),
    (400,'normal','Teor de Arsênio (mg/kg)','Absorção Atómica','<0,1','<0,04'),
    (410,'normal','Teor de Chumbo (mg/kg)','Absorção Atómica','<0,1','<0,04'),
    (420,'normal','Teor de Ferro (mg/kg)','Absorção Atómica','≤3,0','<1,00'),
    (430,'normal','Teor de Cobre (mg/kg)','Absorção Atómica','≤0,1','<0,04'),
    (440,'section','CARACTERISTICAS SENSORIAIS','','',''),
    (450,'header','Grupo dos Azeites de Oliva Virgem – Tipo: Extra Virgem','','',''),
    (460,'normal','Mediana do Defeito (Md)','Análise Sensorial','Igual a 0 (zero)','0'),
    (470,'normal','Mediana do frutado (Mf)','Análise Sensorial','Maior que 0 (zero)','2.0'),
]


class BoletimAnalisesResultado(models.Model):
    _name = 'boletim.analises.resultado'
    _description = 'Linha de Resultado de Análise'
    _order = 'sequence, id'

    boletim_id      = fields.Many2one('boletim.analises', ondelete='cascade', index=True)
    sequence        = fields.Integer(default=10)
    row_type        = fields.Selection([
        ('normal',  'Normal'),
        ('sub',     'Sub-item'),
        ('header',  'Cabeçalho de sub-secção'),
        ('section', 'Nova secção'),
    ], default='normal', required=True)
    analise         = fields.Char('Análise')
    metodo          = fields.Char('Método')
    limites_legais  = fields.Char('Limites Legais')
    resultado       = fields.Char('Resultado')
