from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    primavera_code = fields.Char(
        string="Codigo Primavera",
        copy=False,
        index=True,
    )
    # Peso líquido do artigo no Primavera (o campo Peso do Odoo é o peso bruto),
    # sincronizado com a mesma precisão (28/10/2026).
    primavera_peso_liquido = fields.Float(
        string="Peso Líquido (kg)",
        digits="Stock Weight",
        copy=False,
        help="Campo PesoLiquido do artigo no Primavera. O campo Peso é o peso bruto.",
    )
    primavera_aviso_pesos = fields.Char(
        string="Aviso de pesos",
        compute="_compute_primavera_aviso_pesos",
        store=True,
        help="Peso bruto ou líquido em falta no Primavera. O Odoo não inventa valores: "
             "corrigir no Primavera.",
    )

    _sql_constraints = [
        (
            "primavera_code_unique",
            "unique(primavera_code)",
            "O codigo Primavera do artigo tem de ser unico.",
        )
    ]

    @api.depends("weight", "primavera_peso_liquido", "default_code", "primavera_code")
    def _compute_primavera_aviso_pesos(self):
        for tmpl in self:
            aviso = False
            if tmpl.primavera_code:
                if tmpl.primavera_peso_liquido and not tmpl.weight:
                    aviso = "Sem peso bruto no Primavera (só tem peso líquido)"
                elif tmpl.weight and not tmpl.primavera_peso_liquido and not (tmpl.default_code or "").upper().startswith("PAL"):
                    aviso = "Sem peso líquido no Primavera (só tem peso bruto)"
            tmpl.primavera_aviso_pesos = aviso
