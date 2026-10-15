import time
from odoo import models, api


class ProjectTask(models.Model):
    _inherit = 'project.task'

    def _set_pending_nav(self, user_ids):
        ICP = self.env['ir.config_parameter'].sudo()
        ts = time.time()
        for uid in user_ids:
            key = f'mirazeite.pending_nav.{uid}'
            val = f'project.task:{self.id}:{ts}'
            param = ICP.search([('key', '=', key)], limit=1)
            if param:
                param.value = val
            else:
                ICP.create({'key': key, 'value': val})

    def _send_assignment_notification(self, new_user_ids):
        if not new_user_ids:
            return
        is_todo = not self.project_id
        title = 'Nova tarefa atribuída' if not is_todo else 'Novo to-do atribuído'
        body = self.name or title
        self._set_pending_nav(new_user_ids)
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        click_action = f"{base_url}/web#model=project.task&id={self.id}&view_type=form"
        self.env['kits.mobile.push.notification'].send_push_notification_with_link(
            notify_user_ids=new_user_ids,
            notification_title=title,
            notification_body=body,
            click_action=click_action,
            image_url=False,
        )

    @api.model
    def create(self, vals):
        res = super().create(vals)
        assigned_ids = res.user_ids.ids
        if assigned_ids:
            res._send_assignment_notification(assigned_ids)
        return res

    def write(self, vals):
        if 'user_ids' in vals:
            old_users = {task.id: task.user_ids.ids for task in self}
        res = super().write(vals)
        if 'user_ids' in vals:
            for task in self:
                prev = set(old_users.get(task.id, []))
                curr = set(task.user_ids.ids)
                new_assigned = list(curr - prev)
                if new_assigned:
                    task._send_assignment_notification(new_assigned)
        return res
