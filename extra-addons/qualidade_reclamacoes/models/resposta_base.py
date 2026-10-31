from odoo import models, fields, api

from .constantes import ESTADOS_RESPOSTA, CATEGORIAS, ORIGENS, GRAVIDADES


class QualidadeRespostaBase(models.AbstractModel):
    """Parte comum às respostas da Qualidade (cliente e fornecedor). Sem tabela própria.

    Cada resposta define a sua reclamacao_id, os campos que vêm da reclamação
    e os anexos (cada uma tem a sua tabela de anexos).
    """
    _name = 'qualidade.resposta.base'
    _description = 'Base comum das Respostas da Qualidade'

    data = fields.Date(string='Data', default=fields.Date.today, required=True)
    estado_resposta = fields.Selection(ESTADOS_RESPOSTA, string='Estado', default='aberto', required=True)

    causa = fields.Text(string='Causa')
    acoes_corretivas = fields.Text(string='Ações Corretivas')
    categoria = fields.Selection(CATEGORIAS, string='Categoria')
    origem = fields.Selection(ORIGENS, string='Origem')
    gravidade = fields.Selection(GRAVIDADES, string='Gravidade')
    data_conclusao = fields.Date(string='Data de Conclusão')
    verificacao_eficacia = fields.Text(string='Verificação de Eficácia')
    data_fecho = fields.Date(string='Data de Fecho')
    aprovado_por_id = fields.Many2one('res.users', string='Aprovado por')
    responsavel_id = fields.Many2one('res.users', string='Responsável')
    observacoes = fields.Text(string='Observações')

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
