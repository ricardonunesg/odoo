from odoo import models, fields


class QualidadeRespostaCliente(models.Model):
    _name = 'qualidade.resposta.cliente'
    _inherit = ['qualidade.resposta.base']
    _description = 'Qualidade - Resposta a Reclamação de Cliente'
    _order = 'data desc, id desc'
    _rec_name = 'reclamacao_id'

    reclamacao_id = fields.Many2one(
        'form.reclama.cliente',
        string='Reclamação (Cliente)',
        required=True,
        ondelete='cascade'
    )

    utilizador_id = fields.Many2one('res.users', related='reclamacao_id.user_id', string='Utilizador', readonly=True)
    armazem = fields.Selection(related='reclamacao_id.armazem', string='Armazém', readonly=True)
    cliente = fields.Char(related='reclamacao_id.cliente', string='Cliente', readonly=True)
    codigo_artigo = fields.Char(related='reclamacao_id.codigo_artigo', string='Código Artigo (legado)', readonly=True)
    descricao_artigo = fields.Char(related='reclamacao_id.descricao_artigo', string='Descrição Artigo (legado)', readonly=True)
    lote = fields.Char(related='reclamacao_id.lote', string='Lote (legado)', readonly=True)
    linha_ids = fields.One2many(related='reclamacao_id.linha_ids', string='Artigos', readonly=True)
    descricao_reclamacao = fields.Text(related='reclamacao_id.descricao_reclamacao', string='Descrição da Reclamação', readonly=True)
    acoes_correcao = fields.Text(related='reclamacao_id.acoes_correcao', string='Ações de Correção', readonly=False)
    anexos_formulario_ids = fields.Many2many(related='reclamacao_id.anexos_ids', string='Anexos do Formulário', readonly=True)

    anexos_ids = fields.Many2many(
        'ir.attachment',
        'qual_resp_cliente_attachment_rel',
        'resp_id', 'attachment_id',
        string='Evidências / Anexos'
    )
