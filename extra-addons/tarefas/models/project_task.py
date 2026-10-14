from odoo import api, fields, models


class ProjectTask(models.Model):
    _inherit = "project.task"

    tarefas_template_id = fields.Many2one("tarefas.template", index=True, copy=False)
    real_create_uid = fields.Many2one(
        "res.users",
        string="Criado realmente por",
        default=lambda self: self.env.user.id,
        readonly=True,
        copy=False,
        index=True,
    )

    def init(self):
        super().init()
        self.env.cr.execute(
            "ALTER TABLE project_task "
            "DROP CONSTRAINT IF EXISTS project_task_private_task_has_no_parent"
        )

    @api.constrains("child_ids", "project_id")
    def _ensure_super_task_is_not_private(self):
        return True

    @api.model
    def get_todo_views_id(self):
        views = super().get_todo_views_id()
        full_task_form_id = self.env["ir.model.data"]._xmlid_to_res_id("project.view_task_form2")
        return [
            (full_task_form_id, view_type) if view_type == "form" else (view_id, view_type)
            for view_id, view_type in views
        ]

    def _get_odoobot_partner_id(self):
        try:
            return self.env.ref('base.partner_root').id
        except Exception:
            return False

    def message_post(self, **kwargs):
        # SÓ a mensagem "Task Created" de tarefas criadas pelo módulo tarefas
        # (com tarefas_template_id) é forçada para OdooBot.
        # Tarefas criadas fora do módulo tarefas mantêm o autor real.
        creation_subtype = self.env.ref('project.mt_task_new', raise_if_not_found=False)
        if (
            creation_subtype
            and kwargs.get('subtype_id') == creation_subtype.id
            and self.tarefas_template_id
        ):
            odoobot_id = self._get_odoobot_partner_id()
            if odoobot_id:
                kwargs['author_id'] = odoobot_id
                kwargs['email_from'] = False
        return super().message_post(**kwargs)

    def write(self, vals):
        # Se está a ser atribuído um stage_id que pertence a um projecto e o task
        # ainda não tem project_id, herda o project_id do stage (evita o erro
        # "You can only set a personal stage on a private task").
        if vals.get('stage_id') and 'project_id' not in vals:
            stage = self.env['project.task.type'].browse(vals['stage_id'])
            stage_project = stage.project_ids[:1]
            if stage_project and any(not t.project_id for t in self):
                vals['project_id'] = stage_project.id
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        real_user_id = self.env.user.id
        # Garantir que real_create_uid fica com o utilizador real
        for v in vals_list:
            v.setdefault('real_create_uid', real_user_id)
        records = super().create(vals_list)
        # Mudar create_uid para OdooBot APENAS nas tarefas com tarefas_template_id
        # (tarefas criadas pelo cron/automatismo do módulo tarefas).
        # As outras (criadas via UI normal) mantêm o utilizador real.
        tarefas_records = records.filtered(lambda r: r.tarefas_template_id)
        odoobot_user = self.env.ref('base.user_root', raise_if_not_found=False)
        if odoobot_user and tarefas_records:
            self.env.cr.execute(
                "UPDATE project_task SET create_uid = %s WHERE id IN %s",
                (odoobot_user.id, tuple(tarefas_records.ids)),
            )
            tarefas_records.invalidate_recordset(['create_uid'])
        return records
