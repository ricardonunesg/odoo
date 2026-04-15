from odoo import models, fields, api

ESTADOS_RESPOSTA = [
    ('aberto', 'Aberto'),
    ('pendente', 'Pendente'),
    ('fechado', 'Fechado'),
]

class FormCliente(models.Model):
    _inherit = 'form.reclama.cliente'

    resposta_ids = fields.One2many('qualidade.resposta.cliente', 'reclamacao_id', string='Respostas (Qualidade)')

    ultima_resposta_estado = fields.Selection(ESTADOS_RESPOSTA, string='Estado Resposta', compute='_compute_ultima_resposta')
    ultima_responsavel_id = fields.Many2one('res.users', string='Responsável', compute='_compute_ultima_resposta')
    ultima_aprovado_por_id = fields.Many2one('res.users', string='Aprovado por', compute='_compute_ultima_resposta')
    ultima_data_conclusao = fields.Date(string='Data Conclusão', compute='_compute_ultima_resposta')
    ultima_categoria = fields.Selection([
        ('qualidade', 'Qualidade'),
        ('seguranca', 'Segurança'),
        ('servico', 'Serviço (Transporte)'),
    ], string='Categoria', compute='_compute_ultima_resposta')
    ultima_origem = fields.Selection([
        ('a1', 'A1 - Arruda'),
        ('a2', 'A2 - Tomar'),
    ], string='Origem', compute='_compute_ultima_resposta')
    ultima_gravidade = fields.Selection([
        ('baixa', 'Baixa'),
        ('media', 'Média'),
        ('alta', 'Alta'),
        ('critica', 'Crítica'),
    ], string='Gravidade', compute='_compute_ultima_resposta')

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

    def action_responder_cliente(self):
        self.ensure_one()
        resposta = self.env['qualidade.resposta.cliente'].search(
            [('reclamacao_id', '=', self.id)],
            order='id desc',
            limit=1
        )
        if resposta:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Responder (Cliente)',
                'res_model': 'qualidade.resposta.cliente',
                'view_mode': 'form',
                'res_id': resposta.id,
                'target': 'new',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': 'Responder (Cliente)',
            'res_model': 'qualidade.resposta.cliente',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_reclamacao_id': self.id},
        }


class FormFornecedor(models.Model):
    _inherit = 'form.reclama.fornecedor'

    resposta_ids = fields.One2many('qualidade.resposta.fornecedor', 'reclamacao_id', string='Respostas (Qualidade)')

    ultima_resposta_estado = fields.Selection(ESTADOS_RESPOSTA, string='Estado Resposta', compute='_compute_ultima_resposta')
    ultima_responsavel_id = fields.Many2one('res.users', string='Responsável', compute='_compute_ultima_resposta')
    ultima_aprovado_por_id = fields.Many2one('res.users', string='Aprovado por', compute='_compute_ultima_resposta')
    ultima_data_conclusao = fields.Date(string='Data Conclusão', compute='_compute_ultima_resposta')
    ultima_categoria = fields.Selection([
        ('qualidade', 'Qualidade'),
        ('seguranca', 'Segurança'),
        ('servico', 'Serviço (Transporte)'),
    ], string='Categoria', compute='_compute_ultima_resposta')
    ultima_origem = fields.Selection([
        ('a1', 'A1 - Arruda'),
        ('a2', 'A2 - Tomar'),
    ], string='Origem', compute='_compute_ultima_resposta')
    ultima_gravidade = fields.Selection([
        ('baixa', 'Baixa'),
        ('media', 'Média'),
        ('alta', 'Alta'),
        ('critica', 'Crítica'),
    ], string='Gravidade', compute='_compute_ultima_resposta')

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

    def action_responder_fornecedor(self):
        self.ensure_one()
        resposta = self.env['qualidade.resposta.fornecedor'].search(
            [('reclamacao_id', '=', self.id)],
            order='id desc',
            limit=1
        )
        if resposta:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Responder (Fornecedor)',
                'res_model': 'qualidade.resposta.fornecedor',
                'view_mode': 'form',
                'res_id': resposta.id,
                'target': 'new',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': 'Responder (Fornecedor)',
            'res_model': 'qualidade.resposta.fornecedor',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_reclamacao_id': self.id},
        }
