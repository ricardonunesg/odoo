{
    "name": "Mirazeite — NIF obrigatório e dedup Primavera",
    "version": "18.0.1.0.0",
    "summary": (
        "Força NIF em novos contactos-empresa, faz merge automático "
        "quando Primavera empurra um cliente/fornecedor com NIF já "
        "existente em Odoo, e limpa emails partilhados nos partners."
    ),
    "author": "Mirazeite",
    "license": "LGPL-3",
    "depends": [
        "contacts",
        "crm",
        "primavera_connector",
    ],
    "data": [],
    "post_init_hook": "post_init",
    "installable": True,
    "application": False,
    "auto_install": False,
}
