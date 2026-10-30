from odoo import models, fields, api


class FormReclamacaoClienteLinha(models.Model):
    _name = 'form.reclama.cliente.linha'
    _description = 'Linha de Artigo - Reclamação de Cliente'
    _order = 'sequence, id'

    form_id = fields.Many2one(
        'form.reclama.cliente',
        string='Reclamação',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(default=10)

    artigo_id = fields.Many2one(
        'product.template',
        string='Artigo ERP',
        domain="[('primavera_code', '!=', False)]",
    )
    codigo_artigo = fields.Char(string='Código Artigo (Primavera)', required=True)
    descricao_artigo = fields.Char(string='Descrição Artigo (Primavera)', required=True)
    lote = fields.Char(string='Lote', required=True)

    @api.onchange('artigo_id')
    def _onchange_artigo_id(self):
        for rec in self:
            if rec.artigo_id:
                rec.codigo_artigo = rec.artigo_id.primavera_code or rec.artigo_id.default_code or False
                rec.descricao_artigo = rec.artigo_id.name or False
