def migrate(cr, version):
    """Cria as colunas dos agrupamentos Artigo e Lote antes de o Odoo carregar o módulo, para ele não as calcular pelo
    ORM (alteraria o "Modificado por/em" de todas as reclamações). São preenchidas por SQL no post-migrate."""
    for tabela in ('form_reclama_cliente', 'form_reclama_fornecedor'):
        for coluna in ('grupo_artigo', 'grupo_lote'):
            cr.execute('ALTER TABLE %s ADD COLUMN IF NOT EXISTS %s varchar' % (tabela, coluna))
