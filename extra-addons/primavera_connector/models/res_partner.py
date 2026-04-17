from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    primavera_customer_code = fields.Char(
        string="Codigo Cliente Primavera",
        copy=False,
        index=True,
    )
    primavera_supplier_code = fields.Char(
        string="Codigo Fornecedor Primavera",
        copy=False,
        index=True,
    )

    _sql_constraints = [
        (
            "primavera_customer_code_unique",
            "unique(primavera_customer_code)",
            "O codigo de cliente Primavera tem de ser unico.",
        ),
        (
            "primavera_supplier_code_unique",
            "unique(primavera_supplier_code)",
            "O codigo de fornecedor Primavera tem de ser unico.",
        )
    ]
