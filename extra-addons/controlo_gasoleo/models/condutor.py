from odoo import models, fields, api

class Condutor(models.Model):
    _name = 'gasoleo.condutor'
    _description = 'Condutores'
    _rec_name = 'nome_completo'

    nome = fields.Char(string='Primeiro Nome', required=True)
    apelido = fields.Char(string='Último Nome', required=True)

    nome_completo = fields.Char(string='Nome', compute='_compute_nome_completo', store=True)

    @api.depends('nome', 'apelido')
    def _compute_nome_completo(self):
        for rec in self:
            primeiro = (rec.nome or '').strip()
            ultimo = (rec.apelido or '').strip()
            rec.nome_completo = ' '.join([x for x in [primeiro, ultimo] if x]).strip()
