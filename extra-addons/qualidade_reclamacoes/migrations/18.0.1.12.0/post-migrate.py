from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Preenche os agrupamentos Artigo e Lote das reclamações existentes, sem mexer no "Modificado por/em"."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    for modelo, tabela in (('form.reclama.cliente', 'form_reclama_cliente'), ('form.reclama.fornecedor', 'form_reclama_fornecedor')):
        registos = env[modelo].search([])
        nomes = registos._nomes_artigos()
        for rec in registos:
            artigo, lote = rec._valores_grupos(nomes)
            cr.execute('UPDATE %s SET grupo_artigo = %%s, grupo_lote = %%s WHERE id = %%s' % tabela, (artigo, lote, rec.id))
