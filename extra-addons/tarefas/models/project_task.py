from odoo import api, fields, models


class ProjectTask(models.Model):
    _inherit = "project.task"

    tarefas_template_id = fields.Many2one("tarefas.template", index=True, copy=False)

    def init(self):
        super().init()
        self.env.cr.execute(
            "ALTER TABLE project_task "
            "DROP CONSTRAINT IF EXISTS project_task_private_task_has_no_parent"
        )

    @api.constrains("child_ids", "project_id")
    def _ensure_super_task_is_not_private(self):
        return True

    def get_todo_views_id(self):
        views = super().get_todo_views_id()
        full_task_form_id = self.env["ir.model.data"]._xmlid_to_res_id("project.view_task_form2")
        return [
            (full_task_form_id, view_type) if view_type == "form" else (view_id, view_type)
            for view_id, view_type in views
        ]
