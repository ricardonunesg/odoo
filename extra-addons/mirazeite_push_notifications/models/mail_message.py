from odoo import api, models


class MailMessage(models.Model):
    _inherit = 'mail.message'

    @api.model_create_multi
    def create(self, vals_list):
        # Desliga o push do Discuss do módulo da Keypress (título "New Message",
        # texto com HTML, ignora silenciar/menções); o nosso está em discuss.channel.
        messages = super(MailMessage, self.with_context(mirazeite_push_skip=True)).create(vals_list)
        return messages.with_env(self.env)
