from odoo import fields, models


class PrimaveraSyncLog(models.Model):
    _name = "primavera.sync.log"
    _description = "Log de Sincronizacao Primavera"
    _order = "create_date desc, id desc"

    connection_id = fields.Many2one("primavera.connection", ondelete="cascade")
    operation = fields.Selection(
        [
            ("connection", "Ligação"),
            ("customers", "Clientes"),
            ("suppliers", "Fornecedores"),
            ("products", "Artigos"),
            ("employees", "Funcionários"),
            ("ecls", "ECLs"),
            ("faturas", "Faturas"),
            ("sync_all", "Sincronização completa"),
            ("validacao_composicoes", "Validação Composições"),
            ("validacao_prep_graso", "Validação Preparado Graso MP.19"),
            ("report_ecls", "Report ECLs alteradas"),
            ("report_fa_br", "Report FAs Brasil"),
            ("alerta_gr_grt", "Alerta GR/GRT por faturar"),
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
