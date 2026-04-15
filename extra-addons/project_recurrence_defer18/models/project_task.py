from odoo import fields, models
from dateutil.relativedelta import relativedelta


class ProjectTask(models.Model):
    _inherit = "project.task"

    x_next_occurrence_date = fields.Date(index=True, copy=False)

    def _compute_next_occurrence_date(self):
        self.ensure_one()
        rec = self.recurrence_id
        base = self.date_deadline or fields.Date.context_today(self)

        interval = getattr(rec, "repeat_interval", None) or getattr(rec, "repeat_every", None) or 1
        unit = getattr(rec, "repeat_unit", None) or "weeks"
        unit = (unit or "weeks").lower()

        if unit in ("day", "days"):
            return base + relativedelta(days=int(interval))
        if unit in ("week", "weeks"):
            return base + relativedelta(weeks=int(interval))
        if unit in ("month", "months"):
            return base + relativedelta(months=int(interval))
        if unit in ("year", "years"):
            return base + relativedelta(years=int(interval))

        return base + relativedelta(weeks=int(interval))

    def write(self, vals):
        """
        Odoo 18: não usamos stage.is_closed (não existe no teu build).
        Adiamos a criação da próxima ocorrência apenas quando a task é fechada via 'state'
        (Done/Canceled), que é o gatilho real do core para recorrências.
        """

        closing_by_state = False
        if "state" in vals:
            closing_by_state = vals["state"] in (
                "1_done",
                "1_canceled",
                "done",
                "cancel",
                "canceled",
                "cancelled",
            )

        if closing_by_state:
            for task in self.filtered(lambda t: t.recurrence_id):
                task.x_next_occurrence_date = task._compute_next_occurrence_date()

            # impede criação imediata da próxima task recorrente
            return super(ProjectTask, self.with_context(defer_next_occurrence=True)).write(vals)

        return super(ProjectTask, self).write(vals)
