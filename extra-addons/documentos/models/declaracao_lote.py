from odoo import api, fields, models


class DeclaracaoLoteTemplate(models.Model):
    _name = "declaracao.lote.template"
    _description = "Modelo de Declaração de Lote"
    _rec_name = "name"
    _order = "sequence, name"

    name     = fields.Char("Nome", required=True)
    sequence = fields.Integer(default=10)
    active   = fields.Boolean(default=True)
    default_morada_id = fields.Many2one("documento.morada", "Morada padrão")

    # Cabeçalho
    show_importador     = fields.Boolean("Importador",          default=True)
    show_distribuidor   = fields.Boolean("Distribuidor",        default=False)
    show_morada_cliente = fields.Boolean("Morada do cliente",   default=True)
    show_contentor      = fields.Boolean("Número de contentor", default=True)
    show_fatura         = fields.Boolean("Fatura",              default=True)
    show_data           = fields.Boolean("Data",                default=True)

    # Linhas
    show_description    = fields.Boolean("Nome do produto",      default=True)
    show_ncm            = fields.Boolean("NCM",                  default=True)
    show_caixas         = fields.Boolean("Quantidade de caixas", default=True)
    show_lote           = fields.Boolean("Número de lote",       default=True)
    show_data_fabricacao = fields.Boolean("Data de fabricação",  default=True)
    show_data_validade  = fields.Boolean("Data de validade",     default=True)

    # Outros
    show_observacoes = fields.Boolean("Observações",     default=False)
    in_english       = fields.Boolean("Em Inglês",       default=False)


class DeclaracaoLote(models.Model):
    _name = "declaracao.lote"
    _description = "Declaração de Lote"
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
    template_id = fields.Many2one("declaracao.lote.template", "Modelo", required=True)
    date        = fields.Date("Data", default=fields.Date.today)
    fatura_id   = fields.Many2one(
        "account.move", "Fatura origem",
        domain=[('primavera_ref', '!=', False), ('move_type', '=', 'out_invoice')],
    )
    fatura_ref     = fields.Char("Fatura")
    importador     = fields.Char("Importador")
    distribuidor   = fields.Char("Distribuidor")
    morada_cliente = fields.Char("Morada")
    contentor      = fields.Char("Contentor")
    observacoes    = fields.Text("Observações")

    morada_id     = fields.Many2one(
        "documento.morada", "Morada",
        default=lambda self: self.env.company.default_report_morada_id,
    )
    morada_street  = fields.Char(related="morada_id.street",  string="Rua",          readonly=True)
    morada_street2 = fields.Char(related="morada_id.street2", string="Rua 2",        readonly=True)
    morada_zip     = fields.Char(related="morada_id.zip",     string="Cód. Postal",  readonly=True)
    morada_city    = fields.Char(related="morada_id.city",    string="Localidade",   readonly=True)
    morada_phone   = fields.Char(related="morada_id.phone",   string="Telefone",     readonly=True)
    morada_email   = fields.Char(related="morada_id.email",   string="Email",        readonly=True)
    morada_vat     = fields.Char(related="morada_id.vat",     string="Contribuinte", readonly=True)
    morada_sede   = fields.Text(related='morada_id.sede',   string='Sede',          readonly=True)

    line_ids = fields.One2many("declaracao.lote.linha", "documento_id", "Linhas")

    # Visibilidade via template
    show_importador      = fields.Boolean(related="template_id.show_importador")
    show_distribuidor    = fields.Boolean(related="template_id.show_distribuidor")
    show_morada_cliente  = fields.Boolean(related="template_id.show_morada_cliente")
    show_contentor       = fields.Boolean(related="template_id.show_contentor")
    show_fatura          = fields.Boolean(related="template_id.show_fatura")
    show_data            = fields.Boolean(related="template_id.show_data")
    show_description     = fields.Boolean(related="template_id.show_description")
    show_ncm             = fields.Boolean(related="template_id.show_ncm")
    show_caixas          = fields.Boolean(related="template_id.show_caixas")
    show_lote            = fields.Boolean(related="template_id.show_lote")
    show_data_fabricacao = fields.Boolean(related="template_id.show_data_fabricacao")
    show_data_validade   = fields.Boolean(related="template_id.show_data_validade")
    show_observacoes     = fields.Boolean(related="template_id.show_observacoes")
    in_english           = fields.Boolean(related="template_id.in_english")

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
        self.fatura_ref = fatura.primavera_ref or fatura.name
        self.importador  = fatura.importador or fatura.partner_id.name or self.importador
        self.distribuidor = fatura.distribuidor or self.distribuidor
        self.contentor   = fatura.contentor or self.contentor
        partner = fatura.partner_id
        if partner:
            parts = [p for p in [
                partner.street, partner.street2,
                partner.zip, partner.city,
                partner.country_id.name,
            ] if p]
            self.morada_cliente = ', '.join(parts)

    def action_load_fatura_lines(self):
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
            caixas  = linha.caixas or int(linha.quantity)
            vals_list.append({
                "documento_id":    self.id,
                "sequence":        (i + 1) * 10,
                "description":     product.name or linha.name or '',
                "ncm":             product.x_ncm or '',
                "caixas":          caixas,
                "lote":            linha.lote if linha.lote and not (linha.lote.startswith('<') and linha.lote.endswith('>')) else '',
                "data_fabricacao": product.x_data_fabricacao,
                "data_validade":   linha.data_validade or product.x_data_validade,
            })
        if vals_list:
            self.env["declaracao.lote.linha"].create(vals_list)
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_confirm(self):
        for rec in self:
            if rec.name == "Novo":
                rec.name = self.env["ir.sequence"].next_by_code_sem_repetir("declaracao.lote", "declaracao.lote") or "Novo"
            rec.state = "confirmed"

    def action_reset_draft(self):
        self.write({"state": "draft"})

    def action_cancel(self):
        self.write({"state": "cancelled"})

    def action_print_pdf(self):
        for rec in self:
            if rec.name == "Novo":
                rec.name = self.env["ir.sequence"].next_by_code_sem_repetir("declaracao.lote", "declaracao.lote") or "Novo"
        return self.env.ref("documentos.action_report_declaracao_lote").report_action(self)


class DeclaracaoLoteLinha(models.Model):
    _name = "declaracao.lote.linha"
    _description = "Linha de Declaração de Lote"
    _order = "sequence, id"

    documento_id     = fields.Many2one("declaracao.lote", required=True, ondelete="cascade", index=True)
    sequence         = fields.Integer(default=10)
    description      = fields.Char("Nome do Produto")
    ncm              = fields.Char("NCM")
    caixas           = fields.Integer("Caixas")
    lote             = fields.Char("Lote")
    data_fabricacao  = fields.Date("Data de Fabricação")
    data_validade    = fields.Date("Data de Validade")
