# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class QualityCustomerComplaint(models.Model):
    _name = 'quality.customer.complaint'
    _description = 'Customer Complaint'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(
        string='Nº Reclamação', default='New', copy=False, readonly=True, tracking=True)
    date = fields.Date(string='Data', default=fields.Date.context_today, tracking=True)
    partner_id = fields.Many2one('res.partner', string='Cliente', tracking=True)
    contact_name = fields.Char(string='Pessoa de contacto')
    email = fields.Char(string='Email')
    phone = fields.Char(string='Telefone')

    product_id = fields.Many2one('product.product', string='Produto')
    lot_ref = fields.Char(string='Lote / Referência')
    order_ref = fields.Char(string='Doc. Origem (SO/Fatura/Guia)')

    complaint_type = fields.Selection([
        ('product', 'Produto'),
        ('service', 'Serviço'),
        ('delivery', 'Entrega/Transporte'),
        ('other', 'Outro'),
    ], string='Tipo de Reclamação', default='product', tracking=True)

    severity = fields.Selection([
        ('critical', 'Crítica'),
        ('major', 'Maior'),
        ('minor', 'Menor'),
    ], string='Severidade', default='minor', tracking=True)

    description = fields.Text(string='Descrição da Reclamação', tracking=True)
    cause_analysis = fields.Text(string='Análise da Causa')
    corrective_actions = fields.Text(string='Ações Corretivas')
    preventive_actions = fields.Text(string='Ações Preventivas')

    responsible_id = fields.Many2one('res.users', string='Responsável', default=lambda self: self.env.user, tracking=True)

    state = fields.Selection([
        ('draft', 'Aberta'),
        ('in_progress', 'Em análise'),
        ('done', 'Concluída'),
        ('cancel', 'Cancelada'),
    ], string='Estado', default='draft', tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('quality.customer.complaint') or _('New')
        return super().create(vals_list)

    def action_start(self):
        for rec in self:
            if rec.state not in ('draft', 'cancel'):
                continue
            rec.state = 'in_progress'

    def action_done(self):
        for rec in self:
            if not rec.corrective_actions:
                raise UserError(_('Defina as ações corretivas antes de concluir.'))
            rec.state = 'done'

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_reset(self):
        self.write({'state': 'draft'})
