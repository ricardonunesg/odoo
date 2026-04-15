from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class RegistoKms(models.Model):
    _name = 'gasoleo.registo.kms'
    _description = 'Registo de Quilómetros e Abastecimentos'

    veiculo_id = fields.Many2one('gasoleo.veiculo', string='Veículo', required=True)
    condutor_id = fields.Many2one('gasoleo.condutor', string='Condutor', required=True)
    deposito_id = fields.Many2one('gasoleo.deposito', string='Depósito', required=True)

    kms = fields.Float(string='Quilómetros', required=True)
    litros = fields.Float(string='Litros Abastecidos', required=True)
    data = fields.Date(string='Data', default=fields.Date.today)

    @api.constrains('litros')
    def _check_litros_positive(self):
        for rec in self:
            if rec.litros <= 0:
                raise ValidationError(_('Os litros têm de ser maior que zero.'))

    def _deposito_subtrair(self, deposito, litros):
        if not deposito or litros <= 0:
            return
        dep = deposito.sudo()
        if dep.litros < litros:
            raise ValidationError(_(
                'Não há litros suficientes no depósito "%s". Disponível: %s | Pedido: %s'
            ) % (dep.localizacao, dep.litros, litros))
        dep.litros -= litros

    def _deposito_adicionar(self, deposito, litros):
        if not deposito or litros <= 0:
            return
        deposito.sudo().litros += litros

    @api.model_create_multi
    def create(self, vals_list):
        depositos_cache = {}
        for vals in vals_list:
            deposito_id = vals.get('deposito_id')
            litros = float(vals.get('litros') or 0.0)
            if deposito_id:
                deposito = depositos_cache.get(deposito_id) or self.env['gasoleo.deposito'].browse(deposito_id)
                depositos_cache[deposito_id] = deposito
                self._deposito_subtrair(deposito, litros)
        return super().create(vals_list)

    def write(self, vals):
        for rec in self:
            old_deposito = rec.deposito_id
            old_litros = rec.litros or 0.0

            new_deposito = old_deposito
            if 'deposito_id' in vals:
                new_deposito = self.env['gasoleo.deposito'].browse(vals.get('deposito_id'))

            new_litros = float(vals.get('litros', old_litros) or 0.0)

            if (new_deposito != old_deposito) or (new_litros != old_litros):
                self._deposito_adicionar(old_deposito, old_litros)
                try:
                    self._deposito_subtrair(new_deposito, new_litros)
                except Exception:
                    self._deposito_subtrair(old_deposito, old_litros)
                    raise
        return super().write(vals)

    def unlink(self):
        for rec in self:
            rec._deposito_adicionar(rec.deposito_id, rec.litros or 0.0)
        return super().unlink()
