from odoo.http import request
from odoo import http
import json


class kits_mobile_app_push_notification(http.Controller):
    @http.route(['/app/set_user_app_token'], type='json', auth='public', website=True, methods=['GET', 'POST'], csrf=False)
    def set_login_user_token(self, **kw):
        data_req = json.loads(request.httprequest.data)
        user_push_notification_kits = request.env['kits.mobile.push.notification'].sudo()
        user_rec_available = user_push_notification_kits.search(
            [('hardware_id', '=', data_req['userDeviceName']), ('partner_id', '=', int(data_req['odooResPatnerId']))], limit=1)
        if not user_rec_available:
            user_push_notification_kits.create({
                'user_login': True,
                'hardware_id': data_req['userDeviceName'],
                'partner_id': int(data_req['odooResPatnerId']),
                'firebase_token': data_req['userPushNotificationToken'],
                'user_id': int(data_req['odooUserId']),
            })
        elif user_rec_available.firebase_token != data_req['userPushNotificationToken']:
            user_rec_available.write({
                'firebase_token': data_req['userPushNotificationToken'],
                'user_login': True
            })
        elif not user_rec_available.user_login:
            user_rec_available.write({
                'user_login': True
            })
        data = {'status': 200, 'message': 'success'}
        return data

    @http.route(['/app/app_user_sign_out'], type='json', auth='public', website=True, methods=['GET', 'POST'], csrf=False)
    def app_user_sign_out(self, **kw):
        data_req = json.loads(request.httprequest.data)
        user_rec_available = request.env['kits.mobile.push.notification'].sudo().search(
            [('hardware_id', '=', data_req['userDeviceName']), ('partner_id', '=', int(data_req['odooResPatnerId'])), ('user_login', '=', True)])
        if user_rec_available:
            user_rec_available.write({'user_login': False
            })
        data = {'status': 200, 'message': 'success'}
        return data

    @http.route(['/app/push_notification_get_user_details'], type='json', auth='public', website=True, methods=['GET', 'POST'], csrf=False)
    def app_push_notification_get_user_details(self, **kw):
        try:
            data_req = json.loads(request.httprequest.data)
            user_rec = request.env['res.users'].sudo().search(
                [('login', '=', data_req['user_login'])], limit=1)
            if user_rec:
                data = {
                    'status': 200,
                    'message': 'success',
                    'user_id': user_rec.id,
                    'name': user_rec.name if user_rec.name else False,
                    "avatar": user_rec.image_1920 if user_rec.image_1920 else False,
                    'partner_id': user_rec.partner_id.id if user_rec.partner_id else False,
                }
                return data
            else:
                return {'status': 200, 'message': 'User record not found !...'}
        except Exception as e:
            return {'status': 200, 'message': str(e)}
