from odoo import models

from .kits_mobile_push_notification import _clean_text


class DiscussChannel(models.Model):
    _inherit = 'discuss.channel'

    def _notify_thread_by_web_push(self, message, recipients_data, msg_vals=False, **kwargs):
        """Push para a app para os mesmos destinatários que o Odoo avisa nos
        canais/conversas (já respeita silenciar, "Nada", "Só menções")."""
        super()._notify_thread_by_web_push(message, recipients_data, msg_vals=msg_vals, **kwargs)
        partner_ids = {r['id'] for r in recipients_data if r.get('notif') == 'web_push'}
        if not partner_ids:
            return
        users = self.env['res.partner'].sudo().browse(partner_ids).user_ids.filtered(
            lambda u: u.active and not u.share)
        if not users:
            return
        body = _clean_text((msg_vals or {}).get('body') or message.body)
        if not body:
            return
        title = self._notify_by_web_push_prepare_payload(message, msg_vals=msg_vals).get('title') or 'Discuss'
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        self.env['kits.mobile.push.notification'].sudo().send_push_notification_with_link(
            notify_user_ids=users.ids,
            notification_title=title,
            notification_body=body,
            click_action=f'{base_url}/odoo/discuss?active_id=discuss.channel_{self.id}',
        )
