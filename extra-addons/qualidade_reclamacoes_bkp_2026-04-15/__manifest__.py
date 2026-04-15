{
    'name': 'Qualidade - Reclamações',
    'version': '1.0.0',
    'summary': 'Gestão de reclamações por Qualidade (respostas e estado)',
    'category': 'Operations',
    'author': 'A tua empresa',
    'depends': ['base', 'formularios'],
    'data': [
        'security/security.xml',
        'security/attachment_access.xml',
        'security/ir.model.access.csv',
        'views/qualidade_cliente_views.xml',
        'views/qualidade_fornecedor_views.xml',
        'views/menu.xml',
    ],
    'application': True,
}
