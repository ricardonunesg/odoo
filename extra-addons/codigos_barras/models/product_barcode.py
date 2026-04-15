from odoo import models, fields, api

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    numero_serie = fields.Char(string="Número de Série")
    ean13_calculado = fields.Char(string="EAN-13", compute="_compute_ean13", store=True)
    codigo_base_ean13 = fields.Char(string="Código Base EAN-13")
    indicador_ean14 = fields.Char(string="Indicador EAN-14", default="1")
    ean14_calculado = fields.Char(string="EAN-14", compute="_compute_ean14", store=True)

    @api.depends('numero_serie')
    def _compute_ean13(self):
        for rec in self:
            if rec.numero_serie and len(rec.numero_serie) <= 4:
                base = "56013971" + rec.numero_serie.zfill(4)
                rec.ean13_calculado = base + self._calculate_check_digit_ean13(base)
            else:
                rec.ean13_calculado = ""

    @api.depends('codigo_base_ean13', 'indicador_ean14')
    def _compute_ean14(self):
        for rec in self:
            if rec.codigo_base_ean13 and rec.indicador_ean14 and len(rec.codigo_base_ean13) == 12:
                base = rec.indicador_ean14 + rec.codigo_base_ean13
                rec.ean14_calculado = base + self._calculate_check_digit_ean14(base)
            else:
                rec.ean14_calculado = ""

    def _calculate_check_digit_ean13(self, code):
        total = 0
        for i, digit in enumerate(code):
            n = int(digit)
            total += n * 3 if i % 2 else n
        return str((10 - (total % 10)) % 10)

    def _calculate_check_digit_ean14(self, code):
        total = 0
        for i, digit in enumerate(code):
            n = int(digit)
            total += n * 1 if i % 2 else n * 3
        return str((10 - (total % 10)) % 10)
