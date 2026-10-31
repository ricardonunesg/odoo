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

    ultima_resposta_estado = fields.Selection(ESTADOS_RESPOSTA, string='Estado Resposta', compute='_compute_ultima_resposta')
    ultima_responsavel_id = fields.Many2one('res.users', string='Responsável', compute='_compute_ultima_resposta')
    ultima_aprovado_por_id = fields.Many2one('res.users', string='Aprovado por', compute='_compute_ultima_resposta')
    ultima_data_conclusao = fields.Date(string='Data Conclusão', compute='_compute_ultima_resposta')
    ultima_categoria = fields.Selection(CATEGORIAS, string='Categoria', compute='_compute_ultima_resposta')
    ultima_origem = fields.Selection(ORIGENS, string='Origem', compute='_compute_ultima_resposta')
    ultima_gravidade = fields.Selection(GRAVIDADES, string='Gravidade', compute='_compute_ultima_resposta')

    ultima_causa = fields.Text(string='Causa', compute='_compute_ultima_resposta')
    ultima_acoes_corretivas = fields.Text(string='Ações Corretivas', compute='_compute_ultima_resposta')
    ultima_verificacao_eficacia = fields.Text(string='Verificação Eficácia', compute='_compute_ultima_resposta')
    ultima_data_fecho = fields.Date(string='Data Fecho', compute='_compute_ultima_resposta')
    ultima_observacoes = fields.Text(string='Observações', compute='_compute_ultima_resposta')

    @api.depends(
        'resposta_ids',
        'resposta_ids.estado_resposta',
        'resposta_ids.responsavel_id',
        'resposta_ids.aprovado_por_id',
        'resposta_ids.data_conclusao',
        'resposta_ids.categoria',
        'resposta_ids.origem',
        'resposta_ids.gravidade',
        'resposta_ids.causa',
        'resposta_ids.acoes_corretivas',
        'resposta_ids.verificacao_eficacia',
        'resposta_ids.data_fecho',
        'resposta_ids.observacoes',
    )
    def _compute_ultima_resposta(self):
        for rec in self:
            respostas = rec.resposta_ids.sorted(key=lambda r: (r.data or fields.Date.today(), r.id))
            ultima = respostas[-1] if respostas else False
            rec.ultima_resposta_estado = ultima.estado_resposta if ultima else False
            rec.ultima_responsavel_id = ultima.responsavel_id if ultima else False
            rec.ultima_aprovado_por_id = ultima.aprovado_por_id if ultima else False
            rec.ultima_data_conclusao = ultima.data_conclusao if ultima else False
            rec.ultima_categoria = ultima.categoria if ultima else False
            rec.ultima_origem = ultima.origem if ultima else False
            rec.ultima_gravidade = ultima.gravidade if ultima else False
            rec.ultima_causa = ultima.causa if ultima else False
            rec.ultima_acoes_corretivas = ultima.acoes_corretivas if ultima else False
            rec.ultima_verificacao_eficacia = ultima.verificacao_eficacia if ultima else False
            rec.ultima_data_fecho = ultima.data_fecho if ultima else False
            rec.ultima_observacoes = ultima.observacoes if ultima else False

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

    resposta_ids = fields.One2many('qualidade.resposta.cliente', 'reclamacao_id', string='Respostas (Qualidade)')

    def action_responder_cliente(self):
        return self._abrir_resposta()


class FormFornecedor(models.Model):
    _name = 'form.reclama.fornecedor'
    _inherit = ['form.reclama.fornecedor', 'qualidade.ultima.resposta.mixin']

    _modelo_resposta = 'qualidade.resposta.fornecedor'
    _titulo_responder = 'Responder (Fornecedor)'

    resposta_ids = fields.One2many('qualidade.resposta.fornecedor', 'reclamacao_id', string='Respostas (Qualidade)')

    def action_responder_fornecedor(self):
        return self._abrir_resposta()
