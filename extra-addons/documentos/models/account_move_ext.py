from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    # Identificação Primavera
    primavera_ref = fields.Char('Ref. Primavera', readonly=True, index=True, copy=False)
    primavera_doc_type = fields.Char('Tipo Doc. Primavera', readonly=True)
    primavera_serie = fields.Char('Série Primavera', readonly=True)
    primavera_num = fields.Integer('Nº Primavera', readonly=True)
    primavera_filial = fields.Char('Filial Primavera', readonly=True)

    # Ligação a ECL e documentos de origem
    primavera_docs_origem = fields.Char('Docs Origem Primavera', readonly=True)
    ecl_sale_order_id = fields.Many2one('sale.order', 'ECL Associada', readonly=True, ondelete='set null')

    # Campos packing list no cabeçalho
    importador = fields.Char('Importador')
    distribuidor = fields.Char('Distribuidor')
    destino = fields.Char('Destino')
    modo_transporte = fields.Char('Modo de Transporte')
    contentor = fields.Char('Nº Contentor')
    pais_destino_id = fields.Many2one('res.country', 'País de Destino')
    ref_cliente = fields.Char('V/Ref Cliente')
    report_morada_id = fields.Many2one(
        'documento.morada',
        'Morada do Relatório',
        default=lambda self: self.env.company.default_report_morada_id,
    )

    # Totais calculados das linhas
    total_caixas = fields.Integer(
        'Total Caixas', compute='_compute_pl_totals', store=True)
    total_peso_liquido = fields.Float(
        'Total P. Líquido (kg)', compute='_compute_pl_totals', store=True, digits=(16, 3))
    total_peso_bruto = fields.Float(
        'Total P. Bruto (kg)', compute='_compute_pl_totals', store=True, digits=(16, 3))
    total_volume = fields.Float(
        'Total Volume (m³)', compute='_compute_pl_totals', store=True, digits=(16, 4))

    @api.depends(
        'invoice_line_ids.caixas', 'invoice_line_ids.peso_liquido',
        'invoice_line_ids.peso_bruto', 'invoice_line_ids.volume',
    )
    def _compute_pl_totals(self):
        for move in self:
            lines = move.invoice_line_ids.filtered(
                lambda l: l.display_type == 'product' and l.product_id
            )
            # Paletes (códigos PAL...) não contam para o peso líquido (só produto)
            non_palete = lines.filtered(
                lambda l: not (l.product_id.default_code or '').upper().startswith('PAL')
            )
            move.total_caixas = sum(lines.mapped('caixas'))
            # Peso/volume são UNITÁRIOS por caixa — multiplicar pela qnt da linha
            # Para paletes (caixas=0), usar quantity para que o peso bruto da palete entre no total
            def qty(l):
                return l.caixas or l.quantity
            move.total_peso_liquido = sum(l.peso_liquido * qty(l) for l in non_palete)
            move.total_peso_bruto = sum(l.peso_bruto * qty(l) for l in lines)
            move.total_volume = sum(l.volume * qty(l) for l in lines)


    def _compute_display_name(self):
        primavera = self.filtered('primavera_ref')
        for move in primavera:
            client = move.partner_id.name or ''
            ref = move.primavera_ref or ''
            parts = [p for p in [client, ref] if p]
            move.display_name = ' – '.join(parts) if parts else ref
        super(AccountMove, self - primavera)._compute_display_name()


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    lote = fields.Char('Lote')
    data_validade = fields.Date('Validade')
    peso_liquido = fields.Float('P. Líquido (kg)', digits='Stock Weight')
    peso_bruto = fields.Float('P. Bruto (kg)', digits='Stock Weight')
    volume = fields.Float('Volume (m³)', digits='Volume')

    def _peso_liquido_unit(self):
        """{id da linha: peso líquido unitário (kg)} — o da linha; sem ele, o PesoLiquido
        do artigo no Primavera, nunca o peso bruto (28/10/2026). Primavera indisponível:
        o peso do artigo, como antes."""
        sem = self.filtered(lambda l: not l.peso_liquido and l.product_id.default_code)
        liquidos = {}
        if sem:
            conn = self.env["primavera.connection"].sudo().search([], limit=1)
            liquidos = conn._primavera_pesos_liquidos(sem.mapped("product_id.default_code")) if conn else None
        return {
            l.id: l.peso_liquido or (
                liquidos.get(l.product_id.default_code, 0.0) if liquidos is not None else l.product_id.weight
            )
            for l in self
        }
    caixas = fields.Integer('Caixas')
    unidades_linha = fields.Float('Unidades Totais', digits=(16, 2))
