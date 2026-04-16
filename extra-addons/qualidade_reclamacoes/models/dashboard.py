from odoo import fields, models, tools


class QualidadeReclamacaoDashboard(models.Model):
    _name = 'qualidade.reclamacao.dashboard'
    _description = 'Dashboard de Reclamações da Qualidade'
    _auto = False
    _order = 'data_criacao desc, id desc'

    tipo = fields.Selection([
        ('cliente', 'Cliente'),
        ('fornecedor', 'Fornecedor'),
    ], string='Tipo', readonly=True)
    reclamacao_ref = fields.Char(string='Reclamação', readonly=True)
    entidade = fields.Char(string='Cliente / Fornecedor', readonly=True)
    utilizador_id = fields.Many2one('res.users', string='Utilizador', readonly=True)
    responsavel_id = fields.Many2one('res.users', string='Responsável', readonly=True)
    aprovado_por_id = fields.Many2one('res.users', string='Aprovado por', readonly=True)
    armazem = fields.Selection([
        ('a1', 'A1 - Arruda'),
        ('a2', 'A2 - Tomar'),
        ('outra', 'Outra'),
    ], string='Armazém', readonly=True)
    estado_resposta = fields.Selection([
        ('sem_resposta', 'Sem Resposta'),
        ('aberto', 'Aberto'),
        ('pendente', 'Pendente'),
        ('fechado', 'Fechado'),
    ], string='Estado', readonly=True)
    categoria = fields.Selection([
        ('qualidade', 'Qualidade'),
        ('seguranca', 'Segurança'),
        ('servico', 'Serviço (Transporte)'),
    ], string='Categoria', readonly=True)
    origem = fields.Selection([
        ('a1', 'A1 - Arruda'),
        ('a2', 'A2 - Tomar'),
    ], string='Origem', readonly=True)
    gravidade = fields.Selection([
        ('baixa', 'Baixa'),
        ('media', 'Média'),
        ('alta', 'Alta'),
        ('critica', 'Crítica'),
    ], string='Gravidade', readonly=True)
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

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    (cliente.id * 2 - 1) AS id,
                    'cliente'::varchar AS tipo,
                    cliente.cliente AS entidade,
                    cliente.user_id AS utilizador_id,
                    cliente.armazem AS armazem,
                    cliente.codigo_artigo AS codigo_artigo,
                    cliente.descricao_artigo AS descricao_artigo,
                    cliente.create_date AS data_criacao,
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
                        THEN resposta.data_fecho - cliente.create_date::date
                        ELSE NULL
                    END::float AS dias_para_fechar,
                    CASE
                        WHEN COALESCE(resposta.estado_resposta, 'sem_resposta') != 'fechado'
                        THEN CURRENT_DATE - cliente.create_date::date
                        ELSE NULL
                    END::float AS dias_em_aberto,
                    (
                        COALESCE(resposta.estado_resposta, 'sem_resposta') != 'fechado'
                        AND CURRENT_DATE - cliente.create_date::date > 7
                    ) AS fora_sla_7,
                    (
                        COALESCE(resposta.estado_resposta, 'sem_resposta') != 'fechado'
                        AND CURRENT_DATE - cliente.create_date::date > 15
                    ) AS fora_sla_15,
                    (
                        COALESCE(resposta.estado_resposta, 'sem_resposta') != 'fechado'
                        AND CURRENT_DATE - cliente.create_date::date > 30
                    ) AS fora_sla_30,
                    (
                        COALESCE(resposta.estado_resposta, 'sem_resposta') != 'fechado'
                        AND resposta.data_conclusao IS NULL
                    ) AS acoes_corretivas_pendentes,
                    'Cliente #' || cliente.id::varchar AS reclamacao_ref,
                    1 AS quantidade
                FROM form_reclama_cliente cliente
                LEFT JOIN LATERAL (
                    SELECT resposta_cliente.*
                    FROM qualidade_resposta_cliente resposta_cliente
                    WHERE resposta_cliente.reclamacao_id = cliente.id
                    ORDER BY resposta_cliente.data DESC NULLS LAST, resposta_cliente.id DESC
                    LIMIT 1
                ) resposta ON TRUE

                UNION ALL

                SELECT
                    (fornecedor.id * 2) AS id,
                    'fornecedor'::varchar AS tipo,
                    fornecedor.fornecedor AS entidade,
                    fornecedor.user_id AS utilizador_id,
                    fornecedor.armazem AS armazem,
                    fornecedor.codigo_artigo AS codigo_artigo,
                    fornecedor.descricao_artigo AS descricao_artigo,
                    fornecedor.create_date AS data_criacao,
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
                        THEN resposta.data_fecho - fornecedor.create_date::date
                        ELSE NULL
                    END::float AS dias_para_fechar,
                    CASE
                        WHEN COALESCE(resposta.estado_resposta, 'sem_resposta') != 'fechado'
                        THEN CURRENT_DATE - fornecedor.create_date::date
                        ELSE NULL
                    END::float AS dias_em_aberto,
                    (
                        COALESCE(resposta.estado_resposta, 'sem_resposta') != 'fechado'
                        AND CURRENT_DATE - fornecedor.create_date::date > 7
                    ) AS fora_sla_7,
                    (
                        COALESCE(resposta.estado_resposta, 'sem_resposta') != 'fechado'
                        AND CURRENT_DATE - fornecedor.create_date::date > 15
                    ) AS fora_sla_15,
                    (
                        COALESCE(resposta.estado_resposta, 'sem_resposta') != 'fechado'
                        AND CURRENT_DATE - fornecedor.create_date::date > 30
                    ) AS fora_sla_30,
                    (
                        COALESCE(resposta.estado_resposta, 'sem_resposta') != 'fechado'
                        AND resposta.data_conclusao IS NULL
                    ) AS acoes_corretivas_pendentes,
                    'Fornecedor #' || fornecedor.id::varchar AS reclamacao_ref,
                    1 AS quantidade
                FROM form_reclama_fornecedor fornecedor
                LEFT JOIN LATERAL (
                    SELECT resposta_fornecedor.*
                    FROM qualidade_resposta_fornecedor resposta_fornecedor
                    WHERE resposta_fornecedor.reclamacao_id = fornecedor.id
                    ORDER BY resposta_fornecedor.data DESC NULLS LAST, resposta_fornecedor.id DESC
                    LIMIT 1
                ) resposta ON TRUE
            )
        """ % self._table)


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
