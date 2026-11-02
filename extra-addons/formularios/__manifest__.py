{
    'web_icon': 'formularios/static/description/icon.png',
    'name': 'Formulários',
    'version': '1.5.2',
    'summary': 'Formulários de reclamações (Cliente e Fornecedor)',
    'category': 'Operations',
    'author': 'A tua empresa',
    'depends': ['base', 'mail', 'primavera_connector'],
    'data': [
        'security/ir.model.access.csv',
        'data/numeracoes.xml',
        'views/form_cliente_views.xml',
        'views/form_fornecedor_views.xml',
        'views/corrigir_tipo_views.xml',
        'views/menu.xml',
        'report/form_cliente_report.xml',
        'report/form_fornecedor_report.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'formularios/static/src/lote_primavera/lote_primavera_field.js',
            'formularios/static/src/lote_primavera/lote_primavera_field.xml',
        ],
    },
    'application': True,
}
