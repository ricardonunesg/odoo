from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    # Base do Odoo + códigos Primavera e nome de fornecedor: num contacto que é
    # cliente e fornecedor a ficha tem o nome/ref de cliente, e sem isto o
    # código FO e o nome de fornecedor não encontravam nada.
    _rec_names_search = [
        "complete_name", "email", "ref", "vat", "company_registry",
        "primavera_customer_code", "primavera_supplier_code", "primavera_supplier_name",
    ]

    primavera_supplier_name = fields.Char(
        string="Nome como fornecedor (Primavera)",
        copy=False,
        readonly=True,
        help="Preenchido pela sincronização de fornecedores quando o contacto também "
             "é cliente e o nome na ficha de fornecedor do Primavera é diferente.",
    )
