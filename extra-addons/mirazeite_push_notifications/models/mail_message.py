import re
import time
from odoo import models, api


class MailMessage(models.Model):
    _inherit = 'mail.message'

    def _set_pending_nav(self, user_ids, model, res_id):
        ICP = self.env['ir.config_parameter'].sudo()
        ts = time.time()
        for uid in user_ids:
            key = f'mirazeite.pending_nav.{uid}'
            val = f'{model}:{res_id}:{ts}'
            param = ICP.search([('key', '=', key)], limit=1)
            if param:
                param.value = val
            else:
                ICP.create({'key': key, 'value': val})

    @api.model
    def create(self, vals):
        res = super().create(vals)
        if res.model == 'project.task' and res.res_id and res.body and res.message_type in ('comment', 'email'):
            task = self.env['project.task'].browse(res.res_id)
            if not task.exists():
                return res
            body = re.sub('<[^>]+>', ' ', res.body).strip()
            if not body:
                return res
            follower_users = task.message_follower_ids.mapped('partner_id.user_ids').filtered(
                lambda u: u.id != res.create_uid.id and not u.share
            )
            if follower_users:
                title = task.name or 'Nova mensagem'
                self._set_pending_nav(follower_users.ids, 'project.task', res.res_id)
                base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
                click_action = f"{base_url}/web#model=project.task&id={res.res_id}&view_type=form"
                self.env['kits.mobile.push.notification'].send_push_notification_with_link(
                    notify_user_ids=follower_users.ids,
                    notification_title=title,
                    notification_body=body,
                    click_action=click_action,
                    image_url=False,
                )
        return res
