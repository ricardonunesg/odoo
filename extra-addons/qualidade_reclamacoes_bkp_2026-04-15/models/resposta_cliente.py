from odoo import models, fields, api

class QualidadeRespostaCliente(models.Model):
    _name = 'qualidade.resposta.cliente'
    _description = 'Qualidade - Resposta a Reclamação de Cliente'
    _order = 'data desc, id desc'
    _rec_name = 'reclamacao_id'

    reclamacao_id = fields.Many2one(
        'form.reclama.cliente',
        string='Reclamação (Cliente)',
        required=True,
        ondelete='cascade'
    )
    data = fields.Date(string='Data', default=fields.Date.today, required=True)

    estado_resposta = fields.Selection([
        ('aberto', 'Aberto'),
        ('pendente', 'Pendente'),
        ('fechado', 'Fechado'),
    ], string='Estado', default='aberto', required=True)

    utilizador_id = fields.Many2one('res.users', related='reclamacao_id.user_id', string='Utilizador', readonly=True)
    armazem = fields.Selection(related='reclamacao_id.armazem', string='Armazém', readonly=True)
    cliente = fields.Char(related='reclamacao_id.cliente', string='Cliente', readonly=True)
    codigo_artigo = fields.Char(related='reclamacao_id.codigo_artigo', string='Código Artigo', readonly=True)
    descricao_artigo = fields.Char(related='reclamacao_id.descricao_artigo', string='Descrição Artigo', readonly=True)
    lote = fields.Char(related='reclamacao_id.lote', string='Lote', readonly=True)
    descricao_reclamacao = fields.Text(related='reclamacao_id.descricao_reclamacao', string='Descrição da Reclamação', readonly=True)
    acoes_correcao = fields.Text(related='reclamacao_id.acoes_correcao', string='Ações de Correção', readonly=False)
    anexos_formulario_ids = fields.Many2many(related='reclamacao_id.anexos_ids', string='Anexos do Formulário', readonly=True)

    causa = fields.Text(string='Causa')
    acoes_corretivas = fields.Text(string='Ações Corretivas')
    categoria = fields.Selection([
        ('qualidade', 'Qualidade'),
        ('seguranca', 'Segurança'),
        ('servico', 'Serviço (Transporte)'),
    ], string='Categoria')
    origem = fields.Selection([
        ('a1', 'A1 - Arruda'),
        ('a2', 'A2 - Tomar'),
    ], string='Origem')
    gravidade = fields.Selection([
        ('baixa', 'Baixa'),
        ('media', 'Média'),
        ('alta', 'Alta'),
        ('critica', 'Crítica'),
    ], string='Gravidade')
    data_conclusao = fields.Date(string='Data de Conclusão')
    verificacao_eficacia = fields.Text(string='Verificação de Eficácia')
    data_fecho = fields.Date(string='Data de Fecho')
    aprovado_por_id = fields.Many2one('res.users', string='Aprovado por')
    responsavel_id = fields.Many2one('res.users', string='Responsável')
    observacoes = fields.Text(string='Observações')

    anexos_ids = fields.Many2many(
        'ir.attachment',
        'qual_resp_cliente_attachment_rel',
        'resp_id', 'attachment_id',
        string='Evidências / Anexos'
    )

    def _normalize_anexos_ids(self):
        for rec in self:
            if not rec.id or not rec.anexos_ids:
                continue
            rec.anexos_ids.sudo().write({
                'res_model': rec._name,
                'res_id': rec.id,
            })

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._normalize_anexos_ids()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'anexos_ids' in vals:
            self._normalize_anexos_ids()
        return res
