{
    'name': 'OCM Mobile Push Notification',
    'summary': "This feature is used to get personalized push notifications for your odoo mobile app",
    'description': "This feature is used to get personalized push notifications for your odoo mobile app",
    'category': 'Technical',
    'version': '18.0.1.1.1',
    'website': 'https://www.ocmobileapp.com',
    'author': 'Keypress IT Services',
    'sequence': 1,
    'data': [
        'security/ir.model.access.csv',
        'views/kits_mobile_push_notification_view.xml'
    ],
    'depends': ['mail','kits_odoo_community_mobile_app'],
    'application': True,
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'external_dependencies': {'python': ['pyjwt']},
    
}
