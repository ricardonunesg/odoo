from odoo import models, fields, api

class Veiculo(models.Model):
    _name = 'gasoleo.veiculo'
    _description = 'Veículos'
    _rec_name = 'nome'

    data_compra = fields.Date(string='Data de Compra')
    marca = fields.Char(string='Marca', required=True)
    modelo = fields.Char(string='Modelo')
    matricula = fields.Char(string='Matrícula', required=True)

    nome = fields.Char(string='Nome', compute='_compute_nome', store=True)

    @api.depends('matricula', 'marca', 'modelo')
    def _compute_nome(self):
        for rec in self:
            matricula = (rec.matricula or '').strip()
            marca = (rec.marca or '').strip()
            modelo = (rec.modelo or '').strip()
            extra = ' '.join([x for x in [marca, modelo] if x]).strip()
            if matricula and extra:
                rec.nome = f"{matricula} | {extra}"
            elif matricula:
                rec.nome = matricula
            elif extra:
                rec.nome = extra
            else:
                rec.nome = ''
