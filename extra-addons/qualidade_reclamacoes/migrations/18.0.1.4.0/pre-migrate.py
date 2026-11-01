"""Prepara os 8 valores guardados da "última resposta" ANTES de o Odoo carregar o módulo.

As colunas são criadas e preenchidas aqui, directamente na base de dados, a partir das respostas
(última = data mais recente; em empate, a criada por último — a mesma regra do código). Assim o Odoo
encontra as colunas já preenchidas e não as recalcula pelo ORM, o que alteraria o "Modificado por/em"
de todas as reclamações históricas.
"""
import logging

_logger = logging.getLogger(__name__)

COLUNAS = [
    ('ultima_resposta_estado', 'varchar', 'estado_resposta'),
    ('ultima_responsavel_id', 'int4', 'responsavel_id'),
    ('ultima_aprovado_por_id', 'int4', 'aprovado_por_id'),
    ('ultima_data_conclusao', 'date', 'data_conclusao'),
    ('ultima_categoria', 'varchar', 'categoria'),
    ('ultima_origem', 'varchar', 'origem'),
    ('ultima_gravidade', 'varchar', 'gravidade'),
    ('ultima_data_fecho', 'date', 'data_fecho'),
]
TABELAS = [('form_reclama_cliente', 'qualidade_resposta_cliente'), ('form_reclama_fornecedor', 'qualidade_resposta_fornecedor')]


def preencher(cr, criar_colunas=False):
    for tabela, respostas in TABELAS:
        if criar_colunas:
            for coluna, tipo, _ in COLUNAS:
                cr.execute('ALTER TABLE %s ADD COLUMN IF NOT EXISTS %s %s' % (tabela, coluna, tipo))
        sets = ', '.join('%s = u.%s' % (coluna, campo) for coluna, _, campo in COLUNAS)
        cr.execute("""
            UPDATE {t} t SET {sets}
            FROM {t} c
            LEFT JOIN LATERAL (
                SELECT r.* FROM {r} r WHERE r.reclamacao_id = c.id ORDER BY r.data DESC, r.id DESC LIMIT 1
            ) u ON TRUE
            WHERE t.id = c.id
        """.format(t=tabela, r=respostas, sets=sets))
        _logger.info('qualidade_reclamacoes: última resposta preenchida em %d reclamações (%s)', cr.rowcount, tabela)


def migrate(cr, version):
    preencher(cr, criar_colunas=True)
