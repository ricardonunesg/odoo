# -*- coding: utf-8 -*-
{
    'name': 'Quality - Customer Complaint (Community)',
    'summary': 'Ficha de Reclamação de Cliente para o Departamento de Qualidade',
    'version': '18.0.1.0.0',
    'category': 'Quality',
    'author': 'Tu',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'contacts', 'product'],
'data': [
    'security/security.xml',
    'security/ir.model.access.csv',
    'data/sequence.xml',
    'views/complaint_views.xml',   # cria a action aqui
    'views/menu.xml',              # menu referencia a action
],
    'application': True,
}
