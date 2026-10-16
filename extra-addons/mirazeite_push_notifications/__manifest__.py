{
    'name': 'Mirazeite Push Notifications',
    'version': '18.0.1.1.1',
    'category': 'Technical',
    'summary': 'Push para a app de telemóvel de tudo o que chega à Caixa de entrada do Discuss',
    'depends': ['kits_mobile_push_notification', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/cron.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
