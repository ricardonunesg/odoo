"""Numera, uma única vez, as reclamações que ainda não têm número (as históricas).

Ordem: data de criação, da mais antiga para a mais recente; em empate, o ID interno.
Usa as próprias séries (ir.sequence), por isso os contadores ficam no número seguinte certo.
Só preenche a coluna "name": não mexe em mais nenhum campo, nas datas de alteração nem nas
ligações a respostas, artigos e anexos (que são feitas pelo ID interno, que não muda).

No fim alinha os contadores: em cada série e ano, o próximo número fica sempre acima do maior
número já usado (protege contra uma série reposta ou recriada, ex.: depois de uma reversão).
"""
import datetime
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

SERIES = {
    'formularios.reclamacao.cliente': ('form_reclama_cliente', 'RCL'),
    'formularios.reclamacao.fornecedor': ('form_reclama_fornecedor', 'RFO'),
    'formularios.reclamacao.interna': ('form_reclama_fornecedor', 'RIN'),
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Seq = env['ir.sequence']
    origens = [
        ('form_reclama_cliente', "'formularios.reclamacao.cliente'"),
        ('form_reclama_fornecedor', "CASE WHEN tipo_reclamacao = 'interna' THEN 'formularios.reclamacao.interna' "
                                    "ELSE 'formularios.reclamacao.fornecedor' END"),
    ]
    _alinhar_contadores(cr, env)
    for tabela, codigo in origens:
        cr.execute("SELECT id, create_date, %s FROM %s WHERE name IS NULL ORDER BY create_date, id" % (codigo, tabela))
        linhas = cr.fetchall()
        for rid, criado, cod in linhas:
            numero = Seq.next_by_code(cod, sequence_date=criado.date())
            if not numero:
                raise ValueError('Numeração %s em falta' % cod)
            cr.execute("UPDATE " + tabela + " SET name = %s WHERE id = %s AND name IS NULL", (numero, rid))
        _logger.info('formularios: %d reclamações numeradas em %s', len(linhas), tabela)
    _alinhar_contadores(cr, env)


def _alinhar_contadores(cr, env):
    """Para cada série e ano já usados: próximo número = maior número usado + 1 (nunca recua)."""
    for codigo, (tabela, prefixo) in SERIES.items():
        seq = env['ir.sequence'].search([('code', '=', codigo)], limit=1)
        if not seq:
            raise ValueError('Numeração %s em falta' % codigo)
        cr.execute("""
            SELECT split_part(n, '/', 2)::int AS ano, max(split_part(n, '/', 3)::int)
            FROM (SELECT name AS n FROM {t} WHERE name LIKE %(p)s
                  UNION ALL
                  SELECT trim(x) FROM {t}, unnest(string_to_array(coalesce(numeros_anteriores, ''), ',')) x
                  WHERE trim(x) LIKE %(p)s) u
            GROUP BY 1
        """.format(t=tabela) if tabela == 'form_reclama_fornecedor' else """
            SELECT split_part(name, '/', 2)::int, max(split_part(name, '/', 3)::int)
            FROM {t} WHERE name LIKE %(p)s GROUP BY 1
        """.format(t=tabela), {'p': prefixo + '/%'})
        for ano, maximo in cr.fetchall():
            dia = datetime.date(ano, 1, 1)
            faixa = env['ir.sequence.date_range'].search(
                [('sequence_id', '=', seq.id), ('date_from', '<=', dia), ('date_to', '>=', dia)], limit=1)
            if not faixa:
                faixa = seq._create_date_range_seq(dia)
            if faixa.number_next <= maximo:
                _logger.info('formularios: contador %s/%s alinhado de %s para %s', prefixo, ano, faixa.number_next, maximo + 1)
                faixa.number_next = maximo + 1
