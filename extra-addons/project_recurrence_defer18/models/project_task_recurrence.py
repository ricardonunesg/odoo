from odoo import api, fields, models

class ProjectTaskRecurrence(models.Model):
    _inherit = "project.task.recurrence"

    def _create_next_occurrence(self, last_task):
        if self.env.context.get("defer_next_occurrence"):
            return False
        return super()._create_next_occurrence(last_task)

    @api.model
    def _cron_create_deferred_occurrences(self):
        today = fields.Date.context_today(self)
        tasks = self.env["project.task"].search([
            ("recurrence_id", "!=", False),
            ("x_next_occurrence_date", "!=", False),
            ("x_next_occurrence_date", "<=", today),
        ])
        last_map = tasks.recurrence_id._get_last_task_id_per_recurrence_id()
        for t in tasks:
            if last_map.get(t.recurrence_id.id) == t.id:
                t.recurrence_id._create_next_occurrence(t)
            t.x_next_occurrence_date = False
