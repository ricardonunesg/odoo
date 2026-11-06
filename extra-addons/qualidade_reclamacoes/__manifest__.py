{
    'web_icon': 'qualidade_reclamacoes/static/description/icon.png',
    'name': 'Qualidade - Reclamações',
    'version': '1.12.0',
    'summary': 'Gestão de reclamações por Qualidade (respostas e estado)',
    'category': 'Operations',
    'author': 'A tua empresa',
    'depends': ['base', 'formularios'],
    'data': [
        'security/security.xml',
        'security/attachment_access.xml',
        'security/ir.model.access.csv',
        'data/notificacao_data.xml',
        'views/rastreabilidade_templates.xml',
        'views/dashboard_views.xml',
        'views/qualidade_cliente_views.xml',
        'views/qualidade_fornecedor_views.xml',
        'views/notificacao_views.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'qualidade_reclamacoes/static/src/anexos_preview/anexos_preview_field.js',
            'qualidade_reclamacoes/static/src/anexos_preview/anexos_preview_field.xml',
            'qualidade_reclamacoes/static/src/abrir_responder/abrir_responder.js',
        ],
    },
    'application': True,
}
