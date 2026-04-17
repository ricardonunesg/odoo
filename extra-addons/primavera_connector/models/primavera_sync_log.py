from odoo import fields, models


class PrimaveraSyncLog(models.Model):
    _name = "primavera.sync.log"
    _description = "Log de Sincronizacao Primavera"
    _order = "create_date desc, id desc"

    connection_id = fields.Many2one("primavera.connection", ondelete="cascade")
    operation = fields.Selection(
        [
            ("connection", "Ligacao"),
            ("customers", "Clientes"),
            ("suppliers", "Fornecedores"),
            ("products", "Artigos"),
            ("sync_all", "Sincronizacao completa"),
        ],
        required=True,
    )
    state = fields.Selection(
        [
            ("success", "Sucesso"),
            ("warning", "Aviso"),
            ("error", "Erro"),
        ],
        required=True,
    )
    message = fields.Text(required=True)
