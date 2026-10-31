from odoo import models, fields, api

from .constantes import INSTALACOES


class CorrigirTipoReclamacao(models.TransientModel):
    """Janela do botão "Corrigir tipo" (Externa <-> Interna), só para administradores.
    O trabalho é feito em form.reclama.fornecedor._corrigir_tipo (que volta a validar no servidor)."""
    _name = 'formularios.corrigir.tipo'
    _description = 'Corrigir tipo de reclamação (Externa / Interna)'

    reclamacao_id = fields.Many2one('form.reclama.fornecedor', string='Reclamação', required=True, readonly=True, ondelete='cascade')
    numero_atual = fields.Char(related='reclamacao_id.name', string='Número actual')
    tipo_atual = fields.Selection(related='reclamacao_id.tipo_reclamacao', string='Tipo actual')
    novo_tipo = fields.Selection([
        ('externa', 'Externa'),
        ('interna', 'Interna'),
    ], string='Novo tipo', required=True)
    instalacao_reclamada = fields.Selection(INSTALACOES, string='Instalação Reclamada')
    fornecedor_partner_id = fields.Many2one(
        'res.partner',
        string='Fornecedor ERP',
        domain="[('primavera_supplier_code', '!=', False)]",
    )
    motivo = fields.Text(string='Motivo da correcção', required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        rec = self.env['form.reclama.fornecedor'].browse(res.get('reclamacao_id'))
        if rec:
            res['novo_tipo'] = 'externa' if rec.tipo_reclamacao == 'interna' else 'interna'
        return res

    def action_confirmar(self):
        self.ensure_one()
        self.reclamacao_id._corrigir_tipo(self.novo_tipo, self.motivo,
                                          instalacao=self.instalacao_reclamada, parceiro=self.fornecedor_partner_id)
        return {'type': 'ir.actions.act_window_close'}
