from odoo import fields, models


class MirazeitePushPending(models.Model):
    _name = 'mirazeite.push.pending'
    _description = 'Push para o telemóvel em espera (horário de silêncio)'
    _order = 'id'

    user_ids = fields.Many2many('res.users', string='Destinatários')
    title = fields.Char(required=True)
    body = fields.Char(required=True)
    click_action = fields.Char()
    image_url = fields.Char()
