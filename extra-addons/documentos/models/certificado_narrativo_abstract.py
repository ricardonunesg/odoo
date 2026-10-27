import re
from odoo import api, fields, models


class CertificadoNarrativoAbstract(models.AbstractModel):
    _name    = 'certificado.narrativo.abstract'
    _description = 'Base abstrata para certificados narrativos'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ── Identidade ──────────────────────────────────────────────────────────
    name = fields.Char('Referência', readonly=True, copy=False, default='Novo')
    state = fields.Selection(
        [('draft', 'Rascunho'), ('confirmed', 'Confirmado'), ('cancelled', 'Cancelado')],
        default='draft', required=True, string='Estado', tracking=True,
    )
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, required=True, readonly=True,
    )
    date     = fields.Date('Data', default=fields.Date.today)
    fatura_id = fields.Many2one(
        'account.move', 'Fatura origem',
        domain=[('primavera_ref', '!=', False), ('move_type', '=', 'out_invoice')],
    )

    # ── Cliente ──────────────────────────────────────────────────────────────
    importador     = fields.Char('Importador / Cliente')
    distribuidor   = fields.Char('Distribuidor')
    morada_cliente = fields.Text('Morada')
    cnpj_cliente   = fields.Char('CNPJ / Tax ID')
    orderer        = fields.Char('Orderer')
    morada_orderer = fields.Text('Morada Orderer')

    # ── Identificação do produto ──────────────────────────────────────────────
    tipo_produto        = fields.Char('Produto / Tipo')
    descricao_produtos  = fields.Text('Descrição de produtos')
    total_caixas        = fields.Integer('Total caixas')
    peso_liquido_total  = fields.Float('P.L. Total (Kg)', digits=(16, 3))
    lotes_descricao     = fields.Char('Lote(s)')

    # ── Datas (texto livre) ───────────────────────────────────────────────────
    data_inspecao    = fields.Char('Data de inspeção')
    data_embalamento = fields.Char('Data de embalamento')
    data_validade    = fields.Char('Validade')

    # ── Organoléticas ─────────────────────────────────────────────────────────
    apreciacao = fields.Char(
        'Apreciação / Conclusion',
        default='Normal as to the determinations made.',
    )

    # ── Logística ─────────────────────────────────────────────────────────────
    destino         = fields.Char('Destino')
    modo_transporte = fields.Char('Modo de transporte', placeholder='Ex: Marítimo')
    fatura_ref      = fields.Char('Fatura')

    # ── Letter of Credit (Angola) ─────────────────────────────────────────────
    show_letter_of_credit = fields.Boolean('Incluir Letter of Credit', default=False)
    lc_to_order_of        = fields.Text('To Order Of')
    lc_reference          = fields.Char('Reference')
    lc_freight            = fields.Char('Freight', default='Prepaid')
    lc_consignee          = fields.Text('Consignee')

    # ── Rodapé ────────────────────────────────────────────────────────────────
    local_assinatura = fields.Char('Local de assinatura', default='Lisboa')
    observacoes      = fields.Text('Observações')
    morada_id     = fields.Many2one(
        'documento.morada', 'Morada empresa',
        default=lambda self: self.env.company.default_report_morada_id,
    )
    morada_street  = fields.Char(related='morada_id.street',  string='Rua',          readonly=True)
    morada_street2 = fields.Char(related='morada_id.street2', string='Rua 2',        readonly=True)
    morada_zip     = fields.Char(related='morada_id.zip',     string='Cód. Postal',  readonly=True)
    morada_city    = fields.Char(related='morada_id.city',    string='Localidade',   readonly=True)
    morada_phone   = fields.Char(related='morada_id.phone',   string='Telefone',     readonly=True)
    morada_email   = fields.Char(related='morada_id.email',   string='Email',        readonly=True)
    morada_vat     = fields.Char(related='morada_id.vat',     string='Contribuinte', readonly=True)
    morada_sede   = fields.Text(related="morada_id.sede",   string="Sede",          readonly=True)

    # ── Helpers privados ──────────────────────────────────────────────────────

    @staticmethod
    def _extrair_marca(nome):
        """Extrai marca: palavras MAIÚSCULAS no início do nome do produto."""
        words = nome.split()
        brand = []
        for w in words:
            clean = re.sub(r'[^\w]', '', w)
            if clean and clean == clean.upper() and len(clean) > 1:
                brand.append(w)
            else:
                break
        return ' '.join(brand)

    @staticmethod
    def _inferir_tipo_produto(nome):
        n = nome.lower()
        if 'virgem extra' in n or 'extra virgem' in n or 'extra virgin' in n:
            return 'Extra Virgin Olive Oil'
        if 'azeite' in n or 'olive oil' in n:
            return 'Olive Oil'
        if 'azeitona' in n and 'preta' in n:
            return 'Whole Black Olives'
        if 'azeitona' in n and 'verde' in n:
            return 'Whole Green Olives'
        if 'azeitona' in n:
            return 'Whole Olives'
        if 'tempero' in n:
            return 'Food Seasoning'
        return nome

    @staticmethod
    def _formatar_cnpj(vat):
        """Formata o VAT brasileiro como CNPJ (XX.XXX.XXX/XXXX-XX)."""
        if not vat:
            return vat
        raw = vat.upper()
        if raw.startswith('BR'):
            digits = re.sub(r'\D', '', raw[2:])
            if len(digits) == 14:
                return (f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}"
                        f"/{digits[8:12]}-{digits[12:]}")
        return vat

    # ── Métodos override pelos subtipos ───────────────────────────────────────

    def _get_sequence_code(self):
        """Código da sequência. Override em cada subtipo."""
        return False

    def _get_report_xmlid(self):
        """XML ID do relatório. Override em cada subtipo."""
        return False

    def _organoletica_fk_field(self):
        """Nome do FK em certificado.organoletica.linha. Override em cada subtipo."""
        return False

    # ── onchanges ─────────────────────────────────────────────────────────────

    @api.onchange('fatura_id')
    def _onchange_fatura(self):
        fatura = self.fatura_id
        if not fatura:
            return
        self.fatura_ref = fatura.primavera_ref or fatura.name
        self.importador   = fatura.importador or fatura.partner_id.name or self.importador
        self.distribuidor = fatura.distribuidor or self.distribuidor
        self.destino = (
            fatura.pais_destino_id.name
            if fatura.pais_destino_id
            else fatura.destino or self.destino
        )
        partner = fatura.partner_id
        if partner:
            parts = [p for p in [
                partner.street, partner.street2,
                partner.zip, partner.city,
                partner.country_id.name,
            ] if p]
            self.morada_cliente = '\n'.join(parts)
            self.cnpj_cliente = self._formatar_cnpj(partner.vat)

    @api.onchange('modelo_id')
    def _onchange_modelo(self):
        modelo = getattr(self, 'modelo_id', False)
        if not modelo:
            return
        if modelo.default_morada_id:
            self.morada_id = modelo.default_morada_id
        elif self.company_id.default_report_morada_id:
            self.morada_id = self.company_id.default_report_morada_id
        if hasattr(modelo, 'local_assinatura_padrao') and modelo.local_assinatura_padrao:
            self.local_assinatura = modelo.local_assinatura_padrao
        # Copiar apreciação padrão do template
        if hasattr(modelo, 'default_apreciacao') and modelo.default_apreciacao:
            self.apreciacao = modelo.default_apreciacao
        # Nota: o preset de organoléticas é aplicado no create/write (não no onchange)
        # para evitar conflito com action_carregar_linhas_fatura

    # ── Acção principal ───────────────────────────────────────────────────────

    def action_carregar_linhas_fatura(self):
        self.ensure_one()
        if not self.fatura_id:
            return
        fatura  = self.fatura_id
        partner = fatura.partner_id

        # Cabeçalho
        self.fatura_ref = fatura.primavera_ref or fatura.name
        self.importador   = fatura.importador or partner.name or self.importador
        self.distribuidor = fatura.distribuidor or self.distribuidor
        self.destino = (
            fatura.pais_destino_id.name
            if fatura.pais_destino_id
            else fatura.destino or self.destino
        )
        if partner:
            parts = [p for p in [
                partner.street, partner.street2,
                partner.zip, partner.city,
                partner.country_id.name,
            ] if p]
            self.morada_cliente = '\n'.join(parts)
            self.cnpj_cliente = self._formatar_cnpj(partner.vat)

        # Linhas de produto
        lines = fatura.invoice_line_ids.filtered(
            lambda l: l.display_type == 'product'
            and l.product_id
            and l.product_id.default_code
        )
        if not lines:
            return {"type": "ir.actions.client", "tag": "reload"}

        # Lotes únicos
        lotes = []
        for l in lines:
            lot = l.lote or ''
            if lot and not (lot.startswith('<') and lot.endswith('>')) and lot not in lotes:
                lotes.append(lot)
        self.lotes_descricao = ', '.join(lotes)

        # Totais
        self.total_caixas = sum(l.caixas or int(l.quantity) for l in lines)
        self.peso_liquido_total = sum(
            (l.caixas or int(l.quantity)) * (l.peso_liquido or l.product_id.weight or 0.0)
            for l in lines
        )

        # Tipo produto (inferir do primeiro produto)
        first = lines[0]
        self.tipo_produto = self._inferir_tipo_produto(first.product_id.name or '')

        # Descrição de produtos (agrupa por nome de produto único)
        visto = {}
        for l in lines:
            nome = l.product_id.name or ''
            cx   = l.caixas or int(l.quantity)
            visto[nome] = visto.get(nome, 0) + cx
        desc_lines = []
        for nome, cx in visto.items():
            marca = self._extrair_marca(nome)
            resto = nome[len(marca):].strip() if marca else nome
            desc_lines.append(f"{(marca + ' ') if marca else ''}{resto} – {cx} boxes")
        self.descricao_produtos = '\n'.join(desc_lines)

        # Datas do primeiro produto
        fab = first.product_id.x_data_fabricacao
        if fab:
            self.data_embalamento = f"{fab.month:02d}/{fab.year}"
        val = first.data_validade or first.product_id.x_data_validade
        if val:
            self.data_validade = f"{val.month:02d}/{val.year}"

        # Presets organoléticas
        modelo   = getattr(self, 'modelo_id', False)
        fk_field = self._organoletica_fk_field()
        if modelo and fk_field and hasattr(modelo, 'preset_id') and modelo.preset_id:
            # Apaga linhas existentes e copia do preset
            self.env['certificado.organoletica.linha'].search(
                [(fk_field, '=', self.id)]
            ).unlink()
            for pl in modelo.preset_id.linha_ids:
                self.env['certificado.organoletica.linha'].create({
                    fk_field:         self.id,
                    'sequence':       pl.sequence,
                    'caracteristica': pl.caracteristica,
                    'valor':          pl.valor,
                })

        return {"type": "ir.actions.client", "tag": "reload"}

    # ── Estado ────────────────────────────────────────────────────────────────

    def action_confirm(self):
        for rec in self:
            if rec.name == 'Novo':
                seq = rec._get_sequence_code()
                if seq:
                    rec.name = self.env['ir.sequence'].next_by_code(seq) or 'Novo'
            rec.state = 'confirmed'

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_print_pdf(self):
        xmlid = self._get_report_xmlid()
        if not xmlid:
            return
        for rec in self:
            if rec.name == 'Novo':
                seq = rec._get_sequence_code()
                if seq:
                    rec.name = self.env['ir.sequence'].next_by_code(seq) or 'Novo'
        return self.env.ref(xmlid).report_action(self)
