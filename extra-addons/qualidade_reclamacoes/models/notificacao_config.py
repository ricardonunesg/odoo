from odoo import api, fields, models
from odoo.exceptions import ValidationError


class QualidadeNotificacaoConfig(models.Model):
    """Quem trata e quem é avisado de cada reclamação nova, por tipo. 3 linhas fixas (Clientes, Fornecedores,
    Internas), editadas só por administradores. Os emails formais não dependem desta configuração."""
    _name = 'qualidade.notificacao.config'
    _description = 'Qualidade - Responsáveis e notificações'
    _order = 'id'
    _rec_name = 'nome'

    def _dominio_qualidade(self):
        return [('groups_id', 'in', self.env.ref('qualidade_reclamacoes.group_qualidade_eng').id)]

    tipo = fields.Selection([('cliente', 'Clientes'), ('fornecedor', 'Fornecedores'), ('interna', 'Internas')],
                            string='Tipo', required=True, readonly=True)
    nome = fields.Char(string='Reclamações', required=True, readonly=True)
    ativo = fields.Boolean(string='Ativo', default=False)
    responsavel_id = fields.Many2one('res.users', string='Responsável principal', domain=_dominio_qualidade)
    informado_ids = fields.Many2many('res.users', 'qualidade_notificacao_config_users_rel', 'config_id', 'user_id',
                                     string='Informados', domain=_dominio_qualidade)
    prazo_dias = fields.Integer(string='Prazo (dias)', required=True, default=7)

    _sql_constraints = [('tipo_unico', 'unique(tipo)', 'Só pode existir uma linha por tipo de reclamação.')]

    @api.constrains('prazo_dias')
    def _check_prazo(self):
        if any(rec.prazo_dias < 1 for rec in self):
            raise ValidationError("O prazo tem de ser de pelo menos 1 dia.")
