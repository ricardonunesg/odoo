import time
from odoo import http
from odoo.http import request


class PendingNavController(http.Controller):

    @http.route('/mirazeite/pending_nav', type='json', auth='user', methods=['POST'])
    def get_pending_nav(self):
        key = f'mirazeite.pending_nav.{request.env.uid}'
        param = request.env['ir.config_parameter'].sudo().search([('key', '=', key)], limit=1)
        if not param:
            return {}
        try:
            model, res_id, ts = param.value.split(':')
            param.unlink()
            if time.time() - float(ts) < 600:
                return {'model': model, 'res_id': int(res_id)}
        except Exception:
            param.unlink()
        return {}
