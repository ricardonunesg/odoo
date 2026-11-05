from odoo import models, fields, api
from odoo.exceptions import UserError

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

    # Link "Imprimir PDF da reclamação" na ficha do Responder: é um link (não um botão), por isso
    # abre o PDF noutro separador sem gravar a resposta. Calculado, não fica guardado.
    pdf_reclamacao_url = fields.Char(string='PDF da Reclamação', compute='_compute_pdf_reclamacao_url')

    @api.depends('reclamacao_id')
    def _compute_pdf_reclamacao_url(self):
        for rec in self:
            reclamacao = rec.reclamacao_id
            rid = reclamacao._origin.id or reclamacao.id
            rec.pdf_reclamacao_url = ('/report/pdf/%s/%s' % (self.env.ref(reclamacao._relatorio).report_name, rid)
                                      if rid else False)

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
        records.reclamacao_id._sincronizar_atividade()
        return records

    def write(self, vals):
        # a resposta fica sempre na reclamação onde foi criada (no ecrã o campo é só de leitura)
        if 'reclamacao_id' in vals and any(rec.reclamacao_id.id != vals['reclamacao_id'] for rec in self):
            raise UserError("Uma resposta não pode ser mudada para outra reclamação. Se foi feita na reclamação "
                            "errada, um administrador elimina-a e responde-se na reclamação certa.")
        res = super().write(vals)
        if 'anexos_ids' in vals:
            self._normalize_anexos_ids()
        if 'estado_resposta' in vals or 'data' in vals:
            self.reclamacao_id._sincronizar_atividade()
        return res

    def unlink(self):
        reclamacoes = self.reclamacao_id
        res = super().unlink()
        reclamacoes.exists()._sincronizar_atividade()
        return res
