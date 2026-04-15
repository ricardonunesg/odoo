from odoo import fields, models


class ProjectTask(models.Model):
    _inherit = "project.task"

    tarefas_template_id = fields.Many2one("tarefas.template", index=True, copy=False)
