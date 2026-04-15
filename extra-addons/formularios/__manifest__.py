{
    'name': 'Formulários',
    'version': '1.0.0',
    'summary': 'Formulários de reclamações (Cliente e Fornecedor)',
    'category': 'Operations',
    'author': 'A tua empresa',
    'depends': ['base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/form_cliente_views.xml',
        'views/form_fornecedor_views.xml',
        'views/menu.xml',
        'report/form_cliente_report.xml',
        'report/form_fornecedor_report.xml',
    ],
    'application': True,
}
