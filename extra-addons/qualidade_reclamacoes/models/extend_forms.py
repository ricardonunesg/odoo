from odoo import models, fields, api

from .constantes import ESTADOS_RESPOSTA, CATEGORIAS, ORIGENS, GRAVIDADES


class QualidadeUltimaRespostaMixin(models.AbstractModel):
    """Campos "última resposta" e botão Responder, comuns às reclamações de cliente
    e de fornecedor. Sem tabela própria; cada reclamação define resposta_ids e
    _modelo_resposta / _titulo_responder."""
    _name = 'qualidade.ultima.resposta.mixin'
    _description = 'Base comum - Última Resposta da Qualidade'

    _modelo_resposta = None
    _titulo_responder = None
    _campo_lote = None  # nome do campo do lote nas linhas e no cabeçalho (cliente: lote; fornecedor: lote_guia_fatura)

    # Artigos das linhas para as listas da Qualidade: um por linha na mesma célula (Text → o Odoo mostra as quebras),
    # pela ordem das linhas, alinhados entre as 3 colunas. Sem linhas: campos antigos do cabeçalho. Não guardados.
    artigos_codigo = fields.Text(string='Código Artigo', compute='_compute_artigos_lista')
    artigos_descricao = fields.Text(string='Descrição Artigo', compute='_compute_artigos_lista')
    artigos_lote = fields.Text(string='Lote / Guia / Fatura', compute='_compute_artigos_lista')

    # Guardados (para filtrar e agrupar nas listas da Qualidade); recalculados sempre que uma resposta
    # é criada, alterada (incluindo a data) ou eliminada. Sem respostas ficam vazios ("Sem resposta").
    ultima_resposta_estado = fields.Selection(ESTADOS_RESPOSTA, string='Estado Resposta', compute='_compute_ultima_resposta_guardada', store=True)
    ultima_responsavel_id = fields.Many2one('res.users', string='Responsável', compute='_compute_ultima_resposta_guardada', store=True)
    ultima_aprovado_por_id = fields.Many2one('res.users', string='Aprovado por', compute='_compute_ultima_resposta_guardada', store=True)
    ultima_data_conclusao = fields.Date(string='Data Conclusão', compute='_compute_ultima_resposta_guardada', store=True)
    ultima_categoria = fields.Selection(CATEGORIAS, string='Categoria', compute='_compute_ultima_resposta_guardada', store=True)
    ultima_origem = fields.Selection(ORIGENS, string='Origem', compute='_compute_ultima_resposta_guardada', store=True)
    ultima_gravidade = fields.Selection(GRAVIDADES, string='Gravidade', compute='_compute_ultima_resposta_guardada', store=True)
    ultima_data_fecho = fields.Date(string='Data Fecho', compute='_compute_ultima_resposta_guardada', store=True)

    # Textos longos: continuam calculados só quando se vêem
    ultima_causa = fields.Text(string='Causa', compute='_compute_ultima_resposta')
    ultima_acoes_corretivas = fields.Text(string='Ações Corretivas', compute='_compute_ultima_resposta')
    ultima_verificacao_eficacia = fields.Text(string='Verificação Eficácia', compute='_compute_ultima_resposta')
    ultima_observacoes = fields.Text(string='Observações', compute='_compute_ultima_resposta')

    def _ultima_resposta(self):
        """A última resposta: a de data mais recente (em empate, a criada por último)."""
        self.ensure_one()
        respostas = self.resposta_ids.sorted(key=lambda r: (r.data or fields.Date.today(), r.id))
        return respostas[-1] if respostas else False

    @api.depends(
        'resposta_ids',
        'resposta_ids.data',
        'resposta_ids.estado_resposta',
        'resposta_ids.responsavel_id',
        'resposta_ids.aprovado_por_id',
        'resposta_ids.data_conclusao',
        'resposta_ids.categoria',
        'resposta_ids.origem',
        'resposta_ids.gravidade',
        'resposta_ids.data_fecho',
    )
    def _compute_ultima_resposta_guardada(self):
        for rec in self:
            ultima = rec._ultima_resposta()
            rec.ultima_resposta_estado = ultima.estado_resposta if ultima else False
            rec.ultima_responsavel_id = ultima.responsavel_id if ultima else False
            rec.ultima_aprovado_por_id = ultima.aprovado_por_id if ultima else False
            rec.ultima_data_conclusao = ultima.data_conclusao if ultima else False
            rec.ultima_categoria = ultima.categoria if ultima else False
            rec.ultima_origem = ultima.origem if ultima else False
            rec.ultima_gravidade = ultima.gravidade if ultima else False
            rec.ultima_data_fecho = ultima.data_fecho if ultima else False

    @api.depends(
        'resposta_ids',
        'resposta_ids.data',
        'resposta_ids.causa',
        'resposta_ids.acoes_corretivas',
        'resposta_ids.verificacao_eficacia',
        'resposta_ids.observacoes',
    )
    def _compute_ultima_resposta(self):
        for rec in self:
            ultima = rec._ultima_resposta()
            rec.ultima_causa = ultima.causa if ultima else False
            rec.ultima_acoes_corretivas = ultima.acoes_corretivas if ultima else False
            rec.ultima_verificacao_eficacia = ultima.verificacao_eficacia if ultima else False
            rec.ultima_observacoes = ultima.observacoes if ultima else False

    def _depends_artigos_lista(self):
        if not self._campo_lote:  # a própria base comum (sem linhas)
            return []
        return ['linha_ids', 'linha_ids.sequence', 'linha_ids.codigo_artigo', 'linha_ids.descricao_artigo',
                'linha_ids.' + self._campo_lote, 'codigo_artigo', 'descricao_artigo', self._campo_lote]

    @api.depends(lambda self: self._depends_artigos_lista())
    def _compute_artigos_lista(self):
        for rec in self:
            linhas = [(l.codigo_artigo, l.descricao_artigo, l[rec._campo_lote]) for l in rec.linha_ids] \
                or [(rec.codigo_artigo, rec.descricao_artigo, rec[rec._campo_lote])]
            if not any(any(linha) for linha in linhas):
                rec.artigos_codigo = rec.artigos_descricao = rec.artigos_lote = False
                continue
            # "—" num valor vazio mantém o alinhamento das 3 colunas
            rec.artigos_codigo = '\n'.join(c or '—' for c, d, lt in linhas)
            rec.artigos_descricao = '\n'.join(d or '—' for c, d, lt in linhas)
            rec.artigos_lote = '\n'.join(lt or '—' for c, d, lt in linhas)

    def _abrir_resposta(self):
        self.ensure_one()
        resposta = self.env[self._modelo_resposta].search(
            [('reclamacao_id', '=', self.id)],
            order='id desc',
            limit=1
        )
        if resposta:
            return {
                'type': 'ir.actions.act_window',
                'name': self._titulo_responder,
                'res_model': self._modelo_resposta,
                'view_mode': 'form',
                'res_id': resposta.id,
                'target': 'new',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': self._titulo_responder,
            'res_model': self._modelo_resposta,
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_reclamacao_id': self.id},
        }


class FormCliente(models.Model):
    _name = 'form.reclama.cliente'
    _inherit = ['form.reclama.cliente', 'qualidade.ultima.resposta.mixin']

    _modelo_resposta = 'qualidade.resposta.cliente'
    _titulo_responder = 'Responder (Cliente)'
    _campo_lote = 'lote'

    resposta_ids = fields.One2many('qualidade.resposta.cliente', 'reclamacao_id', string='Respostas (Qualidade)')

    def action_responder_cliente(self):
        return self._abrir_resposta()


class FormFornecedor(models.Model):
    _name = 'form.reclama.fornecedor'
    _inherit = ['form.reclama.fornecedor', 'qualidade.ultima.resposta.mixin']

    _modelo_resposta = 'qualidade.resposta.fornecedor'
    _titulo_responder = 'Responder (Fornecedor)'
    _campo_lote = 'lote_guia_fatura'

    resposta_ids = fields.One2many('qualidade.resposta.fornecedor', 'reclamacao_id', string='Respostas (Qualidade)')

    def action_responder_fornecedor(self):
        return self._abrir_resposta()
