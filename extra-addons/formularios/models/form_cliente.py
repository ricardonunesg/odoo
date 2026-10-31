from odoo import models, fields, api

from .constantes import EMAILS_FIXOS  # noqa: F401 (mantido para quem o importava daqui)


class FormReclamacaoCliente(models.Model):
    _name = 'form.reclama.cliente'
    _inherit = ['formularios.reclamacao.base']
    _description = 'Formulário - Reclamações de Cliente'
    _rec_name = 'cliente'

    _campo_parceiro = 'cliente_partner_id'
    _campo_nome = 'cliente'
    _campo_lote = 'lote'
    _titulo_lote = 'Lote'
    _modelo_linha = 'form.reclama.cliente.linha'
    _relatorio = 'formularios.action_report_form_cliente'
    _prefixo_pdf = 'Formulario_Cliente'

    cliente_partner_id = fields.Many2one(
        'res.partner',
        string='Cliente ERP',
        domain="[('primavera_customer_code', '!=', False)]",
    )
    cliente = fields.Char(string='Cliente', required=True)
    lote = fields.Char(string='Lote (legado)')

    # Múltiplos artigos por reclamação
    linha_ids = fields.One2many(
        'form.reclama.cliente.linha', 'form_id',
        string='Artigos',
    )

    anexos_ids = fields.Many2many(
        'ir.attachment',
        'form_reclama_cliente_attachment_rel',
        'form_id', 'attachment_id',
        string='Documento da Reclamação',
        help='Email do cliente, whatsapp do cliente, documentos enviados pelo cliente, fotos, etc.'
    )

    @api.onchange('cliente_partner_id')
    def _onchange_cliente_partner_id(self):
        for rec in self:
            rec.cliente = rec.cliente_partner_id.display_name or False

    def _textos_email(self):
        return (
            'Foi criado um novo formulário de reclamação de cliente.',
            f"<strong>Cliente:</strong> {self.cliente or ''}",
            f'Nova Reclamação de Cliente - {self.cliente or ""}',
        )
