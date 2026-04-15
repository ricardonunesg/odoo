from odoo import api, fields, models
from odoo.addons.project.models.project_task import CLOSED_STATES
from dateutil.relativedelta import relativedelta


class ProjectTask(models.Model):
    _inherit = "project.task"

    def _inverse_state(self):
        """Block immediate next occurrence creation when closing before deadline."""
        today = fields.Date.context_today(self)
        last_task_id_per_recurrence_id = self.recurrence_id._get_last_task_id_per_recurrence_id()

        for task in self:
            if not task.recurrence_id:
                continue
            if task.state in CLOSED_STATES and task.id == last_task_id_per_recurrence_id.get(task.recurrence_id.id):
                deadline = task.date_deadline
                if deadline:
                    deadline = fields.Date.to_date(deadline)
                if deadline and deadline > today:
                    continue
                task.recurrence_id._create_next_occurrence(task)


class ProjectTaskRecurrence(models.Model):
    _inherit = "project.task.recurrence"

    @api.model
    def _cron_generate_recurring_tasks(self):
        """
        Create next occurrences when due (based on last task deadline + recurrence interval),
        even if the previous task is still open.
        """
        today = fields.Date.context_today(self)
        Task = self.env["project.task"].sudo()

        tasks = Task.search([("recurrence_id", "!=", False), ("date_deadline", "!=", False)])
        if not tasks:
            return

        last_map = tasks.recurrence_id._get_last_task_id_per_recurrence_id()

        # loop each recurrence only once
        for rec in tasks.recurrence_id:
            last_task_id = last_map.get(rec.id)
            if not last_task_id:
                continue

            last_task = Task.browse(last_task_id)
            if not last_task.date_deadline:
                continue

            last_deadline = fields.Date.to_date(last_task.date_deadline)

            interval = getattr(rec, "repeat_interval", None) or getattr(rec, "repeat_every", None) or 1
            unit = getattr(rec, "repeat_unit", None) or "weeks"
            unit = (unit or "weeks").lower()

            def add_step(d):
                if unit in ("day", "days"):
                    return d + relativedelta(days=int(interval))
                if unit in ("week", "weeks"):
                    return d + relativedelta(weeks=int(interval))
                if unit in ("month", "months"):
                    return d + relativedelta(months=int(interval))
                if unit in ("year", "years"):
                    return d + relativedelta(years=int(interval))
                return d + relativedelta(weeks=int(interval))

            next_deadline = add_step(last_deadline)

            # create only when due; create only one step per run
            if next_deadline <= today:
                rec._create_next_occurrence(last_task)

    def _create_next_occurrence(self, last_task):
        """Extra safety: never create immediately if last deadline is still in the future."""
        today = fields.Date.context_today(self)
        if last_task and last_task.date_deadline:
            deadline = fields.Date.to_date(last_task.date_deadline)
            if deadline and deadline > today:
                return False
        return super()._create_next_occurrence(last_task)
