{
    'name': 'Controlo de Gasóleo',
    'version': '1.2.3',
    'summary': 'Controlo de veículos, condutores, quilómetros e depósitos de gasóleo',
    'category': 'Operations',
    'author': 'A tua empresa',
    'depends': ['base', 'mail'],
    'data': [
        # ✅ NOVO: grupos (tem de vir antes dos menus)
        'security/security.xml',

        # (mantém o teu access.csv)
        'security/ir.model.access.csv',

        'data/cron.xml',

        'views/veiculo_views.xml',
        'views/condutor_views.xml',
        'views/registo_kms_views.xml',
        'views/deposito_views.xml',
        'views/entrada_deposito_views.xml',

        # menus no fim
        'views/menu.xml',
    ],
    'application': True,
}
