from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    primavera_code = fields.Char(
        string="Codigo Primavera",
        copy=False,
        index=True,
    )

    _sql_constraints = [
        (
            "primavera_code_unique",
            "unique(primavera_code)",
            "O codigo Primavera do artigo tem de ser unico.",
        )
    ]
