import base64
import json
import requests

from odoo import fields, models


class kits_mobile_push_notification(models.Model):
    _name = 'kits.mobile.push.notification'
    _rec_name = 'hardware_id'
    _description = 'Odoo Community Mobile App Users for Push Notification'

    hardware_id = fields.Char('Hardware Id')
    firebase_token = fields.Char('Token')
    partner_id = fields.Many2one('res.partner', 'Partner Id')
    user_id = fields.Many2one('res.users', 'User Id')
    user_login = fields.Boolean('User Login')

    def kits_send_push_notification(self,notify_user_ids,notification_title,notification_body):
        # notify_user_ids : List of User ids , type integer List.
        # notification_title : Title of notification, type String.
        # notification_body :  Notification message, type String.
        self.send_push_notification_with_link(
                notify_user_ids = notify_user_ids.ids, 
                notification_title = notification_title, 
                notification_body = notification_body, 
                click_action=False, 
                image_url=False)


    def send_push_notification_with_link(self, notify_user_ids, notification_title, notification_body, click_action=False, image_url=False):
        # notify_user_ids : List of User ids , type integer List.
        # notification_title : Title of notification, type String.
        # notification_body :  Notification message, type String.
        # click_action : Pass redirect link, when users will click on the notification they will redirect to this link, type String
        # image_url : Pass the image link which will be going to display in the notification, type String
         if notify_user_ids:
            try:
                hardware_ids = self.env['kits.mobile.push.notification'].search(
                    [('user_id', 'in', notify_user_ids), ('user_login', '=', True)])
                method = self.env['connect.server'].sudo().get_method('push_notification', 'send_push_notification_with_link',{})
                if method['method']:
                    localdict = {
                        'hardware_ids': [{'firebase_token': hw.firebase_token} for hw in hardware_ids],
                        'notification_body': notification_body,
                        'notification_title': notification_title,
                        'click_action': click_action,
                        'image_url': image_url,
                    }
                    exec(method['method'], localdict)
            except Exception as e:
                pass
