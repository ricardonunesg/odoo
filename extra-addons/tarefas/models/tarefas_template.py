from odoo import api, fields, models
from dateutil.relativedelta import relativedelta


class TarefasTemplate(models.Model):
    _name = "tarefas.template"
    _description = "Template de Tarefas Agendadas"
    _order = "active desc, next_run_date asc, name"

    name = fields.Char("Nome do modelo", required=True)
    task_name = fields.Char("Nome da tarefa", help="Nome que será atribuído às tarefas criadas. Se vazio, usa o nome do modelo.")
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
    shared_task = fields.Boolean(
        string="Tarefa partilhada",
        default=False,
        help="Se activo, cria UMA única tarefa atribuída a todos os utilizadores. "
             "Se um deles a marcar como Done, fica Done para todos. "
             "Caso contrário, é criada uma tarefa separada para cada utilizador.",
    )

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

            tasks_criadas = Task.browse()
            tasks_assignees = {}  # task_id -> [user_id, user_id, ...]
            if t.shared_task:
                # UMA única tarefa atribuída a todos
                user_ids = t.user_ids.ids
                task = Task.create({
                    "name": t.task_name or t.name,
                    "user_ids": [(6, 0, user_ids)],
                    "date_deadline": run_date,
                    "description": t.description or "",
                    "tarefas_template_id": t.id,
                })
                task.write({"user_ids": [(6, 0, user_ids)]})
                tasks_criadas |= task
                tasks_assignees[task.id] = user_ids
            else:
                # Uma task por utilizador
                for u in t.user_ids:
                    task = Task.create({
                        "name": t.task_name or t.name,
                        "user_ids": [(6, 0, [u.id])],
                        "date_deadline": run_date,
                        "description": t.description or "",
                        "tarefas_template_id": t.id,
                    })
                    task.write({"user_ids": [(6, 0, [u.id])]})
                    tasks_criadas |= task
                    tasks_assignees[task.id] = [u.id]

            # Followers: manter apenas os assignees reais (limpar o utilizador que correu o cron)
            if tasks_criadas:
                Follower = self.env['mail.followers'].sudo()
                User = self.env['res.users'].sudo()
                for task in tasks_criadas:
                    desired_user_ids = tasks_assignees.get(task.id, [])
                    desired_partner_ids = User.browse(desired_user_ids).mapped('partner_id').ids
                    # Apagar todos os followers actuais
                    Follower.search([
                        ('res_model', '=', 'project.task'),
                        ('res_id', '=', task.id),
                    ]).unlink()
                    # Voltar a subscrever apenas os assignees
                    if desired_partner_ids:
                        task.message_subscribe(partner_ids=desired_partner_ids)

            # Avançar agenda
            t.next_run_date = t._next_date(run_date)
