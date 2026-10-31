from odoo import fields, models, tools

from .constantes import ARMAZENS, ESTADOS_RESPOSTA, CATEGORIAS, ORIGENS, GRAVIDADES

# Um bloco SELECT por origem (clientes / fornecedores). O SQL é igual nos dois:
# só mudam a tabela, o alias, o id, o tipo, a entidade e a referência.
_SQL_BLOCO = """
                SELECT
                    {id_expr} AS id,
                    {tipo_expr}::varchar AS tipo,
                    {a}.{entidade} AS entidade,
                    {a}.user_id AS utilizador_id,
                    {a}.armazem AS armazem,
                    {a}.codigo_artigo AS codigo_artigo,
                    {a}.descricao_artigo AS descricao_artigo,
                    {a}.create_date AS data_criacao,
                    COALESCE(resposta.estado_resposta, 'sem_resposta') AS estado_resposta,
                    resposta.categoria AS categoria,
                    resposta.origem AS origem,
                    resposta.gravidade AS gravidade,
                    resposta.responsavel_id AS responsavel_id,
                    resposta.aprovado_por_id AS aprovado_por_id,
                    resposta.data AS data_resposta,
                    resposta.data_conclusao AS data_conclusao,
                    resposta.data_fecho AS data_fecho,
                    CASE
                        WHEN resposta.data_fecho IS NOT NULL
                        THEN resposta.data_fecho - {a}.create_date::date
                        ELSE NULL
                    END::float AS dias_para_fechar,
                    CASE
                        WHEN COALESCE(resposta.estado_resposta, 'sem_resposta') != 'fechado'
                        THEN CURRENT_DATE - {a}.create_date::date
                        ELSE NULL
                    END::float AS dias_em_aberto,
                    (
                        COALESCE(resposta.estado_resposta, 'sem_resposta') != 'fechado'
                        AND CURRENT_DATE - {a}.create_date::date > 7
                    ) AS fora_sla_7,
                    (
                        COALESCE(resposta.estado_resposta, 'sem_resposta') != 'fechado'
                        AND CURRENT_DATE - {a}.create_date::date > 15
                    ) AS fora_sla_15,
                    (
                        COALESCE(resposta.estado_resposta, 'sem_resposta') != 'fechado'
                        AND CURRENT_DATE - {a}.create_date::date > 30
                    ) AS fora_sla_30,
                    (
                        COALESCE(resposta.estado_resposta, 'sem_resposta') != 'fechado'
                        AND resposta.data_conclusao IS NULL
                    ) AS acoes_corretivas_pendentes,
                    CASE WHEN COALESCE(resposta.estado_resposta, 'sem_resposta') = 'fechado' THEN 100 ELSE 0 END::float AS taxa_fecho,
                    (COALESCE(resposta.estado_resposta, 'sem_resposta') != 'fechado' AND CURRENT_DATE - {a}.create_date::date > 7)::int AS qtd_fora_sla_7,
                    (COALESCE(resposta.estado_resposta, 'sem_resposta') != 'fechado' AND CURRENT_DATE - {a}.create_date::date > 15)::int AS qtd_fora_sla_15,
                    (COALESCE(resposta.estado_resposta, 'sem_resposta') != 'fechado' AND CURRENT_DATE - {a}.create_date::date > 30)::int AS qtd_fora_sla_30,
                    {ref_expr} AS reclamacao_ref,
                    1 AS quantidade
                FROM {tabela} {a}
                LEFT JOIN LATERAL (
                    SELECT {r}.*
                    FROM {tabela_resposta} {r}
                    WHERE {r}.reclamacao_id = {a}.id
                    ORDER BY {r}.data DESC NULLS LAST, {r}.id DESC
                    LIMIT 1
                ) resposta ON TRUE
"""

_BLOCOS = [
    dict(  # ids ímpares: clientes
        a='cliente', r='resposta_cliente', entidade='cliente',
        tabela='form_reclama_cliente', tabela_resposta='qualidade_resposta_cliente',
        id_expr='(cliente.id * 2 - 1)',
        tipo_expr="'cliente'",
        ref_expr="'Cliente #' || cliente.id::varchar",
    ),
    dict(  # ids pares: fornecedores (externas e internas)
        a='fornecedor', r='resposta_fornecedor', entidade='fornecedor',
        tabela='form_reclama_fornecedor', tabela_resposta='qualidade_resposta_fornecedor',
        id_expr='(fornecedor.id * 2)',
        tipo_expr="(CASE WHEN fornecedor.tipo_reclamacao = 'interna' THEN 'interna' ELSE 'fornecedor' END)",
        ref_expr="(CASE WHEN fornecedor.tipo_reclamacao = 'interna' THEN 'Interna #' ELSE 'Fornecedor #' END) || fornecedor.id::varchar",
    ),
]


class QualidadeReclamacaoDashboard(models.Model):
    _name = 'qualidade.reclamacao.dashboard'
    _description = 'Dashboard de Reclamações da Qualidade'
    _auto = False
    _order = 'data_criacao desc, id desc'

    tipo = fields.Selection([
        ('cliente', 'Cliente'),
        ('fornecedor', 'Fornecedor'),
        ('interna', 'Interna'),
    ], string='Tipo', readonly=True)
    reclamacao_ref = fields.Char(string='Reclamação', readonly=True)
    entidade = fields.Char(string='Cliente / Fornecedor', readonly=True)
    utilizador_id = fields.Many2one('res.users', string='Utilizador', readonly=True)
    responsavel_id = fields.Many2one('res.users', string='Responsável', readonly=True)
    aprovado_por_id = fields.Many2one('res.users', string='Aprovado por', readonly=True)
    armazem = fields.Selection(ARMAZENS, string='Armazém', readonly=True)
    estado_resposta = fields.Selection([('sem_resposta', 'Sem Resposta')] + ESTADOS_RESPOSTA, string='Estado', readonly=True)
    categoria = fields.Selection(CATEGORIAS, string='Categoria', readonly=True)
    origem = fields.Selection(ORIGENS, string='Origem', readonly=True)
    gravidade = fields.Selection(GRAVIDADES, string='Gravidade', readonly=True)
    codigo_artigo = fields.Char(string='Código Artigo', readonly=True)
    descricao_artigo = fields.Char(string='Descrição Artigo', readonly=True)
    data_criacao = fields.Datetime(string='Data da Reclamação', readonly=True)
    data_resposta = fields.Date(string='Data da Resposta', readonly=True)
    data_conclusao = fields.Date(string='Data de Conclusão', readonly=True)
    data_fecho = fields.Date(string='Data de Fecho', readonly=True)
    dias_para_fechar = fields.Float(string='Dias até Fecho', readonly=True)
    dias_em_aberto = fields.Float(string='Dias em Aberto', readonly=True)
    fora_sla_7 = fields.Boolean(string='Fora SLA 7 Dias', readonly=True)
    fora_sla_15 = fields.Boolean(string='Fora SLA 15 Dias', readonly=True)
    fora_sla_30 = fields.Boolean(string='Fora SLA 30 Dias', readonly=True)
    acoes_corretivas_pendentes = fields.Boolean(string='Ações Corretivas Pendentes', readonly=True)
    quantidade = fields.Integer(string='Quantidade', readonly=True)
    # Medidas para comparar os tipos lado a lado (tabela dinâmica "Por Tipo")
    taxa_fecho = fields.Float(string='% Fechadas', readonly=True, aggregator='avg')
    qtd_fora_sla_7 = fields.Integer(string='Qtd. Fora SLA 7 Dias', readonly=True)
    qtd_fora_sla_15 = fields.Integer(string='Qtd. Fora SLA 15 Dias', readonly=True)
    qtd_fora_sla_30 = fields.Integer(string='Qtd. Fora SLA 30 Dias', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        blocos = '\n                UNION ALL\n'.join(_SQL_BLOCO.format(**b) for b in _BLOCOS)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (%s
            )
        """ % (self._table, blocos))

class QualidadeReclamacaoKpi(models.Model):
    _name = 'qualidade.reclamacao.kpi'
    _description = 'Indicadores de Reclamações da Qualidade'
    _auto = False
    _order = 'sequence, id'

    name = fields.Char(string='Indicador', readonly=True)
    value = fields.Float(string='Valor', readonly=True)
    suffix = fields.Char(string='Sufixo', readonly=True)
    category = fields.Selection([
        ('geral', 'Geral'),
        ('sla', 'SLA'),
        ('pendencias', 'Pendências'),
    ], string='Categoria', readonly=True)
    sequence = fields.Integer(string='Sequência', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env['qualidade.reclamacao.dashboard'].init()
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                WITH dados AS (
                    SELECT *
                    FROM qualidade_reclamacao_dashboard
                ),
                base AS (
                    SELECT
                        COUNT(*)::float AS total,
                        COUNT(*) FILTER (WHERE estado_resposta = 'fechado')::float AS fechadas,
                        COUNT(*) FILTER (WHERE estado_resposta = 'sem_resposta')::float AS sem_resposta,
                        COUNT(*) FILTER (WHERE fora_sla_7)::float AS fora_sla_7,
                        COUNT(*) FILTER (WHERE fora_sla_15)::float AS fora_sla_15,
                        COUNT(*) FILTER (WHERE fora_sla_30)::float AS fora_sla_30,
                        COUNT(*) FILTER (WHERE acoes_corretivas_pendentes)::float AS acoes_corretivas_pendentes,
                        COALESCE(AVG(dias_para_fechar) FILTER (WHERE estado_resposta = 'fechado'), 0)::float AS tempo_medio_fecho
                    FROM dados
                )
                SELECT
                    1 AS id,
                    'Total de Reclamações'::varchar AS name,
                    total AS value,
                    ''::varchar AS suffix,
                    'geral'::varchar AS category,
                    10 AS sequence
                FROM base
                UNION ALL
                SELECT
                    2 AS id,
                    '%% Fechadas'::varchar AS name,
                    CASE WHEN total > 0 THEN ROUND((fechadas * 100 / total)::numeric, 1)::float ELSE 0 END AS value,
                    '%%'::varchar AS suffix,
                    'geral'::varchar AS category,
                    20 AS sequence
                FROM base
                UNION ALL
                SELECT
                    3 AS id,
                    'Sem Resposta'::varchar AS name,
                    sem_resposta AS value,
                    ''::varchar AS suffix,
                    'pendencias'::varchar AS category,
                    30 AS sequence
                FROM base
                UNION ALL
                SELECT
                    4 AS id,
                    'Tempo Médio de Fecho'::varchar AS name,
                    ROUND(tempo_medio_fecho::numeric, 1)::float AS value,
                    ' dias'::varchar AS suffix,
                    'geral'::varchar AS category,
                    40 AS sequence
                FROM base
                UNION ALL
                SELECT
                    5 AS id,
                    'Fora SLA 7 Dias'::varchar AS name,
                    fora_sla_7 AS value,
                    ''::varchar AS suffix,
                    'sla'::varchar AS category,
                    50 AS sequence
                FROM base
                UNION ALL
                SELECT
                    6 AS id,
                    'Fora SLA 15 Dias'::varchar AS name,
                    fora_sla_15 AS value,
                    ''::varchar AS suffix,
                    'sla'::varchar AS category,
                    60 AS sequence
                FROM base
                UNION ALL
                SELECT
                    7 AS id,
                    'Fora SLA 30 Dias'::varchar AS name,
                    fora_sla_30 AS value,
                    ''::varchar AS suffix,
                    'sla'::varchar AS category,
                    70 AS sequence
                FROM base
                UNION ALL
                SELECT
                    8 AS id,
                    'Ações Corretivas Pendentes'::varchar AS name,
                    acoes_corretivas_pendentes AS value,
                    ''::varchar AS suffix,
                    'pendencias'::varchar AS category,
                    80 AS sequence
                FROM base
            )
        """ % self._table)
