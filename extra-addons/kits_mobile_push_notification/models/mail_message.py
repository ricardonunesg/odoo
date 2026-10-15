from odoo import models, api


class mail_message(models.Model):
    _inherit = "mail.message"

    @api.model
    def create(self, vals):
        res = super(mail_message, self).create(vals)
        message = vals.get('body') or ''
        notification_title = 'New Message'
        receive_user_ids = self.env['res.users']
        if res.model == 'discuss.channel':
            channel_rec = self.env['discuss.channel'].browse(res.res_id)
            receive_user_ids = (channel_rec.channel_partner_ids.mapped('user_ids') - res.create_uid)
            click_action = False
            if message and len(receive_user_ids):
                # Notification with Click action and Image
                self.env['kits.mobile.push.notification'].send_push_notification_with_link(
                    notify_user_ids = receive_user_ids.ids, 
                    notification_title = notification_title, 
                    notification_body = message, 
                    click_action=click_action, 
                    image_url=False)
        return res
