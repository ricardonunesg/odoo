from odoo import api, models

from .res_partner import AUTO_CONTACT_CTX


class ResUsers(models.Model):
    _inherit = "res.users"

    # A ficha res.partner do utilizador é criada antes do próprio user
    # (via _inherits) — marca-a como automática para ficar isenta de NIF.
    @api.model_create_multi
    def create(self, vals_list):
        return super(
            ResUsers, self.with_context(**{AUTO_CONTACT_CTX: True})
        ).create(vals_list)
