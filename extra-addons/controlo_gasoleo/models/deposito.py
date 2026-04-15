from odoo import models, fields

class Deposito(models.Model):
    _name = 'gasoleo.deposito'
    _description = 'Depósitos de Combustível'
    _rec_name = 'localizacao'

    localizacao = fields.Char(string='Localização', required=True)
    litros = fields.Float(string='Litros no Depósito', required=True, default=0.0)
