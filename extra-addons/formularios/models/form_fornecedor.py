from odoo import models, fields, api
from odoo.exceptions import ValidationError

from .constantes import EMAILS_FIXOS, INSTALACOES  # noqa: F401 (mantidos para quem os importava daqui)


class FormReclamacaoFornecedor(models.Model):
    _name = 'form.reclama.fornecedor'
    _inherit = ['formularios.reclamacao.base']
    _description = 'Formulário - Reclamações de Fornecedor'
    _rec_name = 'fornecedor'

    _campo_parceiro = 'fornecedor_partner_id'
    _campo_nome = 'fornecedor'
    _campo_lote = 'lote_guia_fatura'
    _titulo_lote = 'Lote / Guia / Fatura'
    _modelo_linha = 'form.reclama.fornecedor.linha'
    _relatorio = 'formularios.action_report_form_fornecedor'
    _prefixo_pdf = 'Formulario_Fornecedor'

    tipo_reclamacao = fields.Selection([
        ('externa', 'Externa'),
        ('interna', 'Interna'),
    ], string='Tipo', required=True, default='externa',
       help='Externa: reclamação a um fornecedor do Primavera. '
            'Interna: reclamação a outra instalação da Mirazeite.')
    instalacao_reclamada = fields.Selection(INSTALACOES, string='Instalação Reclamada')

    fornecedor_partner_id = fields.Many2one(
        'res.partner',
        string='Fornecedor ERP',
        domain="[('primavera_supplier_code', '!=', False)]",
    )
    fornecedor = fields.Char(string='Fornecedor', required=True)
    lote_guia_fatura = fields.Char(string='Lote / Guia remessa / Fatura (legado)')

    # Múltiplos artigos por reclamação
    linha_ids = fields.One2many(
        'form.reclama.fornecedor.linha', 'form_id',
        string='Artigos',
    )

    anexos_ids = fields.Many2many(
        'ir.attachment',
        'form_reclama_fornecedor_attachment_rel',
        'form_id', 'attachment_id',
        string='Documento da Reclamação',
        help='Email do fornecedor, whatsapp, documentos enviados pelo fornecedor, fotos, etc.'
    )

    @api.constrains('tipo_reclamacao', 'instalacao_reclamada', 'armazem')
    def _check_instalacao_reclamada(self):
        for rec in self:
            if rec.tipo_reclamacao != 'interna':
                continue
            if not rec.instalacao_reclamada:
                raise ValidationError("Numa reclamação interna é obrigatório indicar a 'Instalação Reclamada'.")
            if rec.instalacao_reclamada == rec.armazem:
                raise ValidationError("A 'Instalação Reclamada' não pode ser a mesma do 'Armazém' de origem.")

    @api.model
    def _nome_instalacao(self, instalacao):
        """Nome guardado em 'fornecedor' numa reclamação interna (listas, email, painéis)."""
        return 'Interna - %s' % (dict(INSTALACOES).get(instalacao) or '?')

    @api.onchange('fornecedor_partner_id')
    def _onchange_fornecedor_partner_id(self):
        for rec in self:
            rec.fornecedor = rec.fornecedor_partner_id.display_name or False

    @api.onchange('tipo_reclamacao', 'instalacao_reclamada')
    def _onchange_tipo_reclamacao(self):
        for rec in self:
            if rec.tipo_reclamacao == 'interna':
                rec.fornecedor_partner_id = False
                rec.fornecedor = rec._nome_instalacao(rec.instalacao_reclamada) if rec.instalacao_reclamada else False
            else:
                rec.instalacao_reclamada = False
                rec.fornecedor = rec.fornecedor_partner_id.display_name or False

    def _prepare_partner_names(self, vals_list):
        for vals in vals_list:
            if vals.get('tipo_reclamacao') == 'interna':
                # Interna: sem fornecedor ERP; o nome vem da instalação reclamada
                vals['fornecedor_partner_id'] = False
                vals['fornecedor'] = self._nome_instalacao(vals.get('instalacao_reclamada'))
        return super()._prepare_partner_names(vals_list)

    def _textos_email(self):
        if self.tipo_reclamacao == 'interna':
            return (
                'Foi criado um novo formulário de reclamação interna.',
                f"<strong>Instalação Reclamada:</strong> {dict(INSTALACOES).get(self.instalacao_reclamada, '')}",
                f'Nova Reclamação Interna - {dict(INSTALACOES).get(self.instalacao_reclamada, "")}',
            )
        return (
            'Foi criado um novo formulário de reclamação de fornecedor.',
            f"<strong>Fornecedor:</strong> {self.fornecedor or ''}",
            f'Nova Reclamação de Fornecedor - {self.fornecedor or ""}',
        )

    def write(self, vals):
        res = super().write(vals)
        if {'tipo_reclamacao', 'instalacao_reclamada'} & set(vals):
            for rec in self.filtered(lambda r: r.tipo_reclamacao == 'interna'):
                nome = rec._nome_instalacao(rec.instalacao_reclamada)
                if rec.fornecedor != nome or rec.fornecedor_partner_id:
                    super(FormReclamacaoFornecedor, rec).write({
                        'fornecedor': nome,
                        'fornecedor_partner_id': False,
                    })
        return res
