from odoo import api, fields, models

_TEXTO_ABERTURA = (
    "A Mirazeite, SA declara que as embalagens fornecidas ao vosso pedido cumprem "
    "os requisitos estabelecidos na legislação em vigor aplicável aos materiais e objectos "
    "destinados a entrar em contacto com alimentos, nomeadamente:"
)

_REGULAMENTOS = (
    "Regulamento (CE) N.º 1935/2004 do Parlamento Europeu e do Conselho, de 27 de Outubro "
    "de 2004, relativo aos materiais e objectos destinados a entrar em contacto com alimentos\n"
    "Regulamento (CE) N.º 2023/2006 da Comissão, de 22 de Dezembro de 2006, relativo às "
    "boas práticas de fabrico de materiais e objectos destinados a entrar em contacto com alimentos\n"
    "Regulamento (UE) N.º 10/2011 da Comissão, de 14 de Janeiro de 2011, relativo a "
    "materiais e objectos plásticos destinados a entrar em contacto com alimentos\n"
    "Regulamento (UE) 2018/213 da Comissão, relativo à utilização do bisfenol A em "
    "vernizes e revestimentos para embalagens de géneros alimentícios"
)

_TEXTO_INTERMEDIO = "Para o efeito, foram fornecidos os seguintes produtos:"


class CertificadoConformidadeTemplate(models.Model):
    _name  = 'certificado.conformidade.alimentar.template'
    _description = 'Modelo de Certificado de Conformidade Alimentar'
    _rec_name = 'name'
    _order = 'sequence, name'

    name     = fields.Char('Nome', required=True)
    sequence = fields.Integer(default=10)
    active   = fields.Boolean(default=True)

    morada_padrao_id         = fields.Many2one('documento.morada', 'Morada padrão')
    local_assinatura_padrao  = fields.Char('Local assinatura padrão', default='Tomar')

    # Textos padrão (copiados para o documento ao seleccionar o modelo)
    texto_abertura_padrao    = fields.Text('Texto de abertura', default=_TEXTO_ABERTURA)
    regulamentos_padrao      = fields.Text('Regulamentos',      default=_REGULAMENTOS,
                                            help='Um regulamento por linha — renderizado como bullets.')
    texto_intermedio_padrao  = fields.Text('Texto intermédio',  default=_TEXTO_INTERMEDIO)

    # Checkboxes de visibilidade
    show_importador     = fields.Boolean('Importador',       default=True)
    show_distribuidor   = fields.Boolean('Distribuidor',     default=False)
    show_texto_abertura  = fields.Boolean('Mostrar texto de abertura',  default=True)
    show_regulamentos    = fields.Boolean('Mostrar regulamentos',        default=True)
    show_texto_intermedio = fields.Boolean('Mostrar texto intermédio',  default=True)
    show_tabela          = fields.Boolean('Mostrar tabela de produtos',  default=True)
    show_data            = fields.Boolean('Mostrar data',                default=True)


class CertificadoConformidadeAlimentar(models.Model):
    _name    = 'certificado.conformidade.alimentar'
    _description = 'Certificado de Conformidade Alimentar'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order   = 'id desc'

    name = fields.Char('Referência', readonly=True, copy=False, default='Novo')
    state = fields.Selection(
        [('draft', 'Rascunho'), ('confirmed', 'Confirmado'), ('cancelled', 'Cancelado')],
        default='draft', required=True, string='Estado', tracking=True,
    )
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, required=True, readonly=True,
    )
    modelo_id = fields.Many2one(
        'certificado.conformidade.alimentar.template', 'Modelo', required=True,
    )
    date      = fields.Date('Data', default=fields.Date.today)
    fatura_id = fields.Many2one(
        'account.move', 'Fatura origem',
        domain=[('primavera_ref', '!=', False), ('move_type', '=', 'out_invoice')],
    )
    fatura_ref = fields.Char('Fatura')

    # Cliente (preenchido da fatura)
    cliente        = fields.Char('Importador / Cliente')
    distribuidor   = fields.Char('Distribuidor')
    morada_cliente = fields.Text('Morada do cliente')

    # Corpo (copiados do modelo, editáveis por documento)
    texto_abertura    = fields.Text('Texto de abertura')
    regulamentos      = fields.Text('Regulamentos',
                                     help='Um regulamento por linha — cada linha é um bullet.')
    texto_intermedio  = fields.Text('Texto intermédio')

    # Linhas de produtos / embalagens
    line_ids = fields.One2many(
        'certificado.conformidade.alimentar.linha', 'parent_id', 'Produtos / Embalagens',
    )

    # Rodapé
    local_assinatura = fields.Char('Local de assinatura', default='Tomar')
    observacoes      = fields.Text('Observações')
    morada_id        = fields.Many2one('documento.morada', 'Morada empresa')
    morada_street    = fields.Char(related='morada_id.street',  readonly=True)
    morada_street2   = fields.Char(related='morada_id.street2', readonly=True)
    morada_zip       = fields.Char(related='morada_id.zip',     readonly=True)
    morada_city      = fields.Char(related='morada_id.city',    readonly=True)
    morada_phone     = fields.Char(related='morada_id.phone',   readonly=True)
    morada_email     = fields.Char(related='morada_id.email',   readonly=True)
    morada_vat       = fields.Char(related='morada_id.vat',     readonly=True)
    morada_sede   = fields.Text(related='morada_id.sede',   string='Sede',          readonly=True)

    # Visibilidade via modelo
    show_importador      = fields.Boolean(related='modelo_id.show_importador')
    show_distribuidor    = fields.Boolean(related='modelo_id.show_distribuidor')
    show_texto_abertura  = fields.Boolean(related='modelo_id.show_texto_abertura')
    show_regulamentos     = fields.Boolean(related='modelo_id.show_regulamentos')
    show_texto_intermedio = fields.Boolean(related='modelo_id.show_texto_intermedio')
    show_tabela           = fields.Boolean(related='modelo_id.show_tabela')
    show_data             = fields.Boolean(related='modelo_id.show_data')

    @api.onchange('modelo_id')
    def _onchange_modelo(self):
        m = self.modelo_id
        if not m:
            return
        if m.morada_padrao_id:
            self.morada_id = m.morada_padrao_id
        elif self.company_id.default_report_morada_id:
            self.morada_id = self.company_id.default_report_morada_id
        if m.local_assinatura_padrao:
            self.local_assinatura = m.local_assinatura_padrao
        self.texto_abertura   = m.texto_abertura_padrao   or self.texto_abertura
        self.regulamentos     = m.regulamentos_padrao     or self.regulamentos
        self.texto_intermedio = m.texto_intermedio_padrao or self.texto_intermedio

    @api.onchange('fatura_id')
    def _onchange_fatura(self):
        fatura = self.fatura_id
        if not fatura:
            return
        self.fatura_ref = fatura.primavera_ref or fatura.name
        self.cliente      = fatura.importador or fatura.partner_id.name or self.cliente
        self.distribuidor = fatura.distribuidor or self.distribuidor
        partner = fatura.partner_id
        if partner:
            parts = [p for p in [
                partner.street, partner.street2,
                partner.zip, partner.city,
                partner.country_id.name,
            ] if p]
            self.morada_cliente = '\n'.join(parts)

    def action_carregar_da_fatura(self):
        """Preenche cabeçalho e cria linhas (editáveis) a partir da fatura."""
        self.ensure_one()
        if not self.fatura_id:
            return
        fatura  = self.fatura_id
        partner = fatura.partner_id
        self.fatura_ref = fatura.primavera_ref or fatura.name
        self.cliente      = fatura.importador or partner.name or self.cliente
        self.distribuidor = fatura.distribuidor or self.distribuidor
        if partner:
            parts = [p for p in [
                partner.street, partner.street2,
                partner.zip, partner.city,
                partner.country_id.name,
            ] if p]
            self.morada_cliente = '\n'.join(parts)
        # Cria uma linha por produto único (paletes/datas/lote ficam vazios)
        self.line_ids.unlink()
        vals_list = []
        seen = {}
        for i, linha in enumerate(
            fatura.invoice_line_ids.filtered(
                lambda l: l.display_type == 'product' and l.product_id
            )
        ):
            pid = linha.product_id.id
            if pid in seen:
                continue
            seen[pid] = True
            lote = linha.lote or ''
            if lote.startswith('<') and lote.endswith('>'):
                lote = ''
            vals_list.append({
                'parent_id':  self.id,
                'sequence':   (i + 1) * 10,
                'descricao':  linha.product_id.name or '',
                'product_id': pid,
                'lote':       lote,
            })
        if vals_list:
            self.env['certificado.conformidade.alimentar.linha'].create(vals_list)
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_confirm(self):
        for rec in self:
            if rec.name == 'Novo':
                rec.name = (
                    self.env['ir.sequence'].next_by_code('certificado.conformidade.alimentar')
                    or 'Novo'
                )
            rec.state = 'confirmed'

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_print_pdf(self):
        for rec in self:
            if rec.name == 'Novo':
                rec.name = (
                    self.env['ir.sequence'].next_by_code('certificado.conformidade.alimentar')
                    or 'Novo'
                )
        return self.env.ref('documentos.action_report_certificado_conformidade').report_action(self)


class CertificadoConformidadeAlimentarLinha(models.Model):
    _name  = 'certificado.conformidade.alimentar.linha'
    _description = 'Linha do Certificado de Conformidade Alimentar'
    _order = 'sequence, id'

    parent_id  = fields.Many2one(
        'certificado.conformidade.alimentar', required=True, ondelete='cascade', index=True,
    )
    sequence   = fields.Integer(default=10)
    product_id = fields.Many2one('product.product', 'Produto (referência interna)',
                                  help='Referência opcional ao produto do Odoo')
    descricao  = fields.Char('Descrição embalagem', required=True,
                               placeholder='Ex: EMB. SERRATA 0,75L Verde 29p')
    quantidade_paletes    = fields.Char('Paletes',
                                         placeholder='Ex: 12 pal')
    data_producao_inicio  = fields.Char('Produção de',
                                         placeholder='Ex: 14/7 ou 14/07/2025')
    data_producao_fim     = fields.Char('Produção até',
                                         placeholder='Ex: 30/07/2025')
    lote       = fields.Char('Lote', placeholder='Ex: 18025VNP')
