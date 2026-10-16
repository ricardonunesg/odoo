from odoo import api, models


class MailNotification(models.Model):
    _inherit = 'mail.notification'

    @api.model_create_multi
    def create(self, vals_list):
        notifications = super().create(vals_list)
        # as mensagens do Discuss têm push próprio (discuss_channel.py); aqui ficam
        # de fora para uma menção num canal não dar dois pushes
        inbox = notifications.filtered(
            lambda n: n.notification_type == 'inbox' and not n.is_read
            and n.mail_message_id.model != 'discuss.channel')
        if inbox:
            self.env['kits.mobile.push.notification'].sudo()._mirazeite_push_inbox(inbox)
        return notifications
