from odoo import _, api, models
from odoo.exceptions import UserError


class IrSequence(models.Model):
    _inherit = "ir.sequence"

    @api.model
    def next_by_code_sem_repetir(self, sequence_code, model_name):
        """Como next_by_code, mas salta os números que já existam no campo name
        de `model_name`. Os contadores dos documentos chegaram a ser repostos a 1
        por actualizações do módulo, o que gerou números repetidos (26/10/2026);
        assim um contador desactualizado nunca volta a dar um número já emitido."""
        Model = self.env[model_name].sudo().with_context(active_test=False)
        for _tentativa in range(1000):
            numero = self.next_by_code(sequence_code)
            if not numero or not Model.search_count([("name", "=", numero)], limit=1):
                return numero
        raise UserError(_("Não foi possível obter um número livre para %s.") % sequence_code)
