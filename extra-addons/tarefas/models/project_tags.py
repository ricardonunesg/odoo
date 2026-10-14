from odoo import api, fields, models

DEPARTAMENTOS = [
    "Financeiro",
    "Inventário",
    "Administrativo",
    "Qualidade",
    "Reuniões",
    "Pessoal",
    "Manutenção",
    "Vendas",
]


class ProjectTags(models.Model):
    _inherit = "project.tags"

    is_departamento = fields.Boolean(string="Departamento", default=False, index=True)

    @api.model
    def _tarefas_init_departamentos(self):
        # Reutiliza etiquetas existentes com o mesmo nome (nome é único) e cria as que faltam.
        for name in DEPARTAMENTOS:
            tag = self.with_context(active_test=False).search([("name", "=ilike", name)], limit=1)
            if tag:
                tag.is_departamento = True
            else:
                self.create({"name": name, "is_departamento": True})
