from odoo import api, fields, models


class PackingList(models.Model):
    _name = "packing.list"
    _description = "Packing List"
    _rec_name = "name"
    _order = "id desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char("Referência", readonly=True, copy=False, default="Novo")
    state = fields.Selection(
        [("draft", "Rascunho"), ("confirmed", "Confirmado"), ("cancelled", "Cancelado")],
        default="draft", required=True, string="Estado",
    )

    template_id = fields.Many2one("packing.list.template", "Modelo", required=True)
    company_id = fields.Many2one(
        "res.company", "Empresa",
        default=lambda self: self.env.company,
        required=True, readonly=True,
    )
    fatura_id = fields.Many2one(
        "account.move", "Fatura origem",
        domain=[('primavera_ref', '!=', False), ('move_type', '=', 'out_invoice')],
    )
    date = fields.Date("Data", default=fields.Date.today)

    # Visibilidade dinâmica via template
    show_importador         = fields.Boolean(related="template_id.show_importador")
    show_distribuidor       = fields.Boolean(related="template_id.show_distribuidor")
    show_destino            = fields.Boolean(related="template_id.show_destino")
    show_modo_transporte    = fields.Boolean(related="template_id.show_modo_transporte")
    show_contentor          = fields.Boolean(related="template_id.show_contentor")
    show_fatura             = fields.Boolean(related="template_id.show_fatura")
    show_product_code       = fields.Boolean(related="template_id.show_product_code")
    show_description        = fields.Boolean(related="template_id.show_description")
    show_lote               = fields.Boolean(related="template_id.show_lote")
    show_data_validade      = fields.Boolean(related="template_id.show_data_validade")
    show_peso_liquido       = fields.Boolean(related="template_id.show_peso_liquido")
    show_peso_bruto         = fields.Boolean(related="template_id.show_peso_bruto")
    show_volume             = fields.Boolean(related="template_id.show_volume")
    show_caixas             = fields.Boolean(related="template_id.show_caixas")
    show_unidades_linha     = fields.Boolean(related="template_id.show_unidades_linha")
    show_total_caixas       = fields.Boolean(related="template_id.show_total_caixas")
    show_total_peso_liquido = fields.Boolean(related="template_id.show_total_peso_liquido")
    show_total_peso_bruto   = fields.Boolean(related="template_id.show_total_peso_bruto")
    show_total_volume       = fields.Boolean(related="template_id.show_total_volume")
    show_morada             = fields.Boolean(related="template_id.show_morada")
    show_data               = fields.Boolean(related="template_id.show_data")
    show_morada_cliente     = fields.Boolean(related="template_id.show_morada_cliente")
    show_ref_cliente        = fields.Boolean(related="template_id.show_ref_cliente")
    show_observacoes        = fields.Boolean(related="template_id.show_observacoes")
    formula_brasil          = fields.Boolean(related="template_id.formula_brasil")
    in_english              = fields.Boolean(related="template_id.in_english")

    # Cabeçalho
    importador      = fields.Char("Importador")
    morada_cliente  = fields.Char("Morada")
    ref_cliente     = fields.Char("V/Ref Cliente")
    distribuidor    = fields.Char("Distribuidor")
    destino         = fields.Char("Destino")
    modo_transporte = fields.Selection([
        ('navio',  'Navio'),
        ('camiao', 'Camião'),
        ('aviao',  'Avião'),
    ], string="Modo de transporte")
    contentor       = fields.Char("Contentor")
    fatura_ref      = fields.Char("Fatura")
    observacoes     = fields.Text("Observações")

    # Footer / Morada
    morada_id     = fields.Many2one(
        "documento.morada", "Morada",
        default=lambda self: self.env.company.default_report_morada_id,
    )
    morada_street  = fields.Char(related="morada_id.street",  string="Rua",          readonly=True)
    morada_street2 = fields.Char(related="morada_id.street2", string="Rua 2",        readonly=True)
    morada_zip     = fields.Char(related="morada_id.zip",     string="Cód. Postal",  readonly=True)
    morada_city    = fields.Char(related="morada_id.city",    string="Localidade",   readonly=True)
    morada_phone   = fields.Char(related="morada_id.phone",   string="Telefone",     readonly=True)

    # Linhas
    line_ids = fields.One2many("packing.list.line", "packing_list_id", "Linhas")

    # Totais calculados — excluem linhas marcadas como palete
    total_caixas = fields.Integer(
        "Total Caixas", compute="_compute_totals", store=True,
    )
    total_peso_liquido = fields.Float(
        "T. Peso Líquido (kg)", compute="_compute_totals", store=True, digits=(16, 3),
    )
    total_peso_bruto = fields.Float(
        "T. Peso Bruto (kg)", compute="_compute_totals", store=True, digits=(16, 3),
    )
    total_volume = fields.Float(
        "T. Volume (m³)", compute="_compute_totals", store=True, digits=(16, 4),
    )

    @api.depends(
        "line_ids.caixas",
        "line_ids.is_palete",
        "line_ids.pliquidot",
        "line_ids.pbrutot",
        "line_ids.volumet",
    )
    def _compute_totals(self):
        for rec in self:
            non_pallet = rec.line_ids.filtered(lambda l: not l.is_palete)
            all_lines  = rec.line_ids
            # Só caixas e peso líquido excluem paletes (paletes não têm produto líquido)
            rec.total_caixas       = sum(non_pallet.mapped("caixas"))
            rec.total_peso_liquido = sum(non_pallet.mapped("pliquidot"))
            # Peso bruto e volume incluem paletes (comportamento do Primavera)
            rec.total_peso_bruto   = sum(all_lines.mapped("pbrutot"))
            rec.total_volume       = sum(all_lines.mapped("volumet"))

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
        self.fatura_ref  = fatura.primavera_ref or fatura.name
        self.importador  = fatura.importador or fatura.partner_id.name or self.importador
        self.ref_cliente = fatura.ref_cliente or self.ref_cliente
        # Morada do cliente a partir do partner
        partner = fatura.partner_id
        if partner:
            parts = [p for p in [
                partner.street, partner.street2,
                partner.zip, partner.city,
                partner.country_id.name,
            ] if p]
            self.morada_cliente = ', '.join(parts)
        self.distribuidor = fatura.distribuidor or self.distribuidor
        self.destino = (
            fatura.pais_destino_id.name
            if fatura.pais_destino_id
            else fatura.destino or self.destino
        )
        self.contentor = fatura.contentor or self.contentor

    def action_load_fatura_lines(self):
        """Limpa as linhas e importa da fatura — apenas linhas COM código de artigo."""
        self.ensure_one()
        if not self.fatura_id:
            return
        self.line_ids.unlink()
        vals_list = []
        for i, linha in enumerate(
            self.fatura_id.invoice_line_ids.filtered(
                lambda l: l.display_type == 'product'
                and l.product_id
                and l.product_id.default_code
            )
        ):
            product = linha.product_id
            caixas = linha.caixas or int(linha.quantity)
            vals_list.append({
                "packing_list_id":  self.id,
                "sequence":         (i + 1) * 10,
                "product_code":     product.default_code,
                "description":      linha.name or '',
                "lote":             linha.lote if linha.lote and not (linha.lote.startswith('<') and linha.lote.endswith('>')) else '',
                "data_validade":    linha.data_validade,
                "peso_liquido":     linha.peso_liquido or product.weight,
                "peso_bruto":       linha.peso_bruto or product.weight,
                "volume":           linha.volume or product.volume,
                "uni":              product.uom_id.name or '',
                "caixas":           caixas,
                "unidades_linha":   0,
            })
        if vals_list:
            self.env["packing.list.line"].create(vals_list)
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_confirm(self):
        for rec in self:
            if rec.name == "Novo":
                rec.name = self.env["ir.sequence"].next_by_code_sem_repetir("packing.list", "packing.list") or "Novo"
            rec.state = "confirmed"

    def action_reset_draft(self):
        self.write({"state": "draft"})

    def action_cancel(self):
        self.write({"state": "cancelled"})

    def action_print_pdf(self):
        for rec in self:
            if rec.name == "Novo":
                rec.name = self.env["ir.sequence"].next_by_code_sem_repetir("packing.list", "packing.list") or "Novo"
        return self.env.ref("documentos.action_report_packing_list").report_action(self)


class PackingListLine(models.Model):
    _name = "packing.list.line"
    _description = "Linha de Packing List"
    _order = "sequence, id"

    def _auto_init(self):
        super()._auto_init()
        # Corrige is_palete para linhas criadas antes deste campo existir
        self.env.cr.execute("""
            UPDATE packing_list_line
            SET is_palete = (UPPER(COALESCE(product_code, '')) LIKE 'PAL%%')
            WHERE is_palete IS DISTINCT FROM (UPPER(COALESCE(product_code, '')) LIKE 'PAL%%')
        """)

    packing_list_id = fields.Many2one("packing.list", required=True, ondelete="cascade", index=True)
    sequence        = fields.Integer(default=10)

    # Identificação
    product_code = fields.Char("Cód. Artigo")
    description  = fields.Char("Descrição")
    lote         = fields.Char("Lote")
    data_validade = fields.Date("Validade")
    is_palete    = fields.Boolean("É Palete", compute="_compute_is_palete", store=True)

    # Unidade
    uni = fields.Char("Uni")

    # Quantidades
    caixas          = fields.Integer("Qnt")
    unidades_linha  = fields.Float("Unidades Totais", digits=(16, 2))

    # Valores unitários (provenientes da fatura, por caixa)
    peso_liquido = fields.Float("P. Líq. Unit. (kg)", digits="Stock Weight")
    peso_bruto   = fields.Float("P. Bruto Unit. (kg)", digits="Stock Weight")
    volume       = fields.Float("Vol. Unit. (m³)", digits="Volume")

    # Fórmulas: totais por linha
    # pliquidoT = caixas × peso_liquido
    pliquidot = fields.Float(
        "P. Líq. Total (kg)",
        compute="_compute_formulas", store=True, digits=(16, 3),
    )
    # pbrutoT = caixas × peso_bruto
    pbrutot = fields.Float(
        "P. Bruto Total (kg)",
        compute="_compute_formulas", store=True, digits=(16, 3),
    )
    # volumeT = caixas × volume
    volumet = fields.Float(
        "Vol. Total (m³)",
        compute="_compute_formulas", store=True, digits=(16, 4),
    )

    @api.depends("product_code")
    def _compute_is_palete(self):
        for line in self:
            code = (line.product_code or "").upper()
            line.is_palete = code.startswith("PAL")

    @api.depends("caixas", "peso_liquido", "peso_bruto", "volume", "is_palete")
    def _compute_formulas(self):
        for line in self:
            if line.is_palete:
                line.pliquidot = 0.0
                line.pbrutot   = line.caixas * line.peso_bruto
                line.volumet   = line.caixas * line.volume
            else:
                line.pliquidot = line.caixas * line.peso_liquido
                line.pbrutot   = line.caixas * line.peso_bruto
                line.volumet   = line.caixas * line.volume
