from odoo import api, fields, models
from dateutil.relativedelta import relativedelta


class TarefasTemplate(models.Model):
    _name = "tarefas.template"
    _description = "Template de Tarefas Agendadas"
    _order = "active desc, next_run_date asc, name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)

    start_date = fields.Date(required=True, default=fields.Date.context_today)
    next_run_date = fields.Date(required=True, index=True, default=fields.Date.context_today)

    interval_number = fields.Integer(required=True, default=1)
    interval_type = fields.Selection(
        [("days", "Dias"), ("weeks", "Semanas"), ("months", "Meses")],
        required=True,
        default="weeks",
    )

    user_ids = fields.Many2many("res.users", string="Utilizadores", required=True)
    allow_overlap = fields.Boolean(string="Permitir tarefas em simultâneo", default=False)

    description = fields.Text()

    def _next_date(self, base_date):
        self.ensure_one()
        n = int(self.interval_number or 1)
        if self.interval_type == "days":
            return base_date + relativedelta(days=n)
        if self.interval_type == "weeks":
            return base_date + relativedelta(weeks=n)
        return base_date + relativedelta(months=n)

    @api.model
    def _cron_generate_tasks(self):
        today = fields.Date.context_today(self)
        templates = self.search([("active", "=", True), ("next_run_date", "<=", today)])
        if not templates:
            return

        Task = self.env["project.task"].sudo()

        for t in templates:
            run_date = t.next_run_date

            # Evitar duplicados por template+data se não permitir overlap
            if not t.allow_overlap:
                existing = Task.search_count([
                    ("tarefas_template_id", "=", t.id),
                    ("date_deadline", "=", run_date),
                ])
                if existing:
                    t.next_run_date = t._next_date(run_date)
                    continue

            # Criar 1 task por utilizador (To Do usa user_ids, não user_id)
            for u in t.user_ids:
                task = Task.with_context(
                    mail_create_nosubscribe=True,
                    mail_auto_subscribe_no_notify=True,
                ).create({
                    "name": t.name,
                    "user_ids": [(6, 0, [u.id])],
                    "date_deadline": run_date,
                    "description": t.description or "",
                    "tarefas_template_id": t.id,
                })

                # Forçar (se algum default meter mais users)
                task.write({
                    "user_ids": [(6, 0, [u.id])],
                })

            # Avançar agenda
            t.next_run_date = t._next_date(run_date)
