from odoo import api, models


class MailNotification(models.Model):
    _inherit = 'mail.notification'

    @api.model_create_multi
    def create(self, vals_list):
        notifications = super().create(vals_list)
        inbox = notifications.filtered(lambda n: n.notification_type == 'inbox' and not n.is_read)
        if inbox:
            self.env['kits.mobile.push.notification'].sudo()._mirazeite_push_inbox(inbox)
        return notifications
