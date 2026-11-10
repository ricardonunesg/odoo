{
    "name": "CRM — Histórico Primavera",
    "version": "18.0.1.2.0",
    "summary": "Botão na oportunidade com as faturas e notas de crédito do cliente no Primavera (consulta em directo, só leitura)",
    "description": """
Botão "Histórico Primavera" na ficha da oportunidade. Abre uma janela que lê
em directo (só SELECT) as faturas e notas de crédito do cliente no Primavera do
ano anterior e do ano corrente, agrupadas por ano, com as linhas de cada
documento. Valores sem IVA, em formato português; notas de crédito a negativo.
Nada é gravado no Odoo: desinstalar o módulo remove o botão e mais nada.
""",
    "category": "Sales/CRM",
    "author": "Mirazeite",
    "depends": ["crm", "account", "primavera_connector"],
    "data": [
        "views/crm_lead_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "mirazeite_crm_historico_primavera/static/src/historico_primavera.js",
            "mirazeite_crm_historico_primavera/static/src/historico_primavera.xml",
            "mirazeite_crm_historico_primavera/static/src/historico_primavera.scss",
        ],
    },
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
