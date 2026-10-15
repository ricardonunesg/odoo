from odoo import api, fields, models

from .kits_mobile_push_notification import _clean_text


class MailMessage(models.Model):
    _inherit = 'mail.message'

    @api.model_create_multi
    def create(self, vals_list):
        # Desliga o push do Discuss do módulo da Keypress (título "New Message",
        # texto com HTML) e envia o nosso, em português e com o texto limpo.
        messages = super(MailMessage, self.with_context(mirazeite_push_skip=True)).create(vals_list)
        messages = messages.with_env(self.env)
        for message in messages.filtered(lambda m: m.model == 'discuss.channel' and m.res_id
                                         and m.message_type == 'comment'):
            message._mirazeite_push_discuss()
        return messages

    def _mirazeite_push_discuss(self):
        self.ensure_one()
        body = _clean_text(self.body)
        if not body:
            return
        channel = self.env['discuss.channel'].sudo().browse(self.res_id).exists()
        if not channel:
            return
        now = fields.Datetime.now()
        members = channel.channel_member_ids.filtered(
            lambda m: m.partner_id
            and m.partner_id != self.author_id
            and m.custom_notifications != 'no_notif'
            and not (m.mute_until_dt and m.mute_until_dt > now)
        )
        if channel.channel_type == 'channel':
            # num canal, quem pediu "só menções" só recebe se for mencionado
            members = members.filtered(
                lambda m: m.custom_notifications != 'mentions' or m.partner_id in self.partner_ids)
        users = members.partner_id.user_ids.filtered(lambda u: u.active and not u.share)
        if not users:
            return
        author = self.author_id.name or 'Mensagem nova'
        if channel.channel_type == 'channel':
            title = f'#{channel.name}'
            body = _clean_text(f'{author}: {body}')
        else:
            title = author
        self.env['kits.mobile.push.notification'].sudo().send_push_notification_with_link(
            notify_user_ids=users.ids,
            notification_title=title,
            notification_body=body,
        )
