import logging
from urllib.parse import urlencode

from odoo import api, models, fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


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

    # Separador "Rastreabilidade": nada é guardado; a consulta ao Primavera (só leitura) só corre quando se liga
    # "Consultar" e funciona também numa resposta ainda por gravar.
    rastreio_linha_id = fields.Many2one(
        'form.reclama.cliente.linha', string='Artigo / lote reclamado',
        compute='_compute_rastreio_escolha', inverse='_inverse_rastreio', readonly=False)
    rastreio_consultar = fields.Boolean(
        string='Consultar no Primavera', compute='_compute_rastreio_escolha', inverse='_inverse_rastreio', readonly=False)
    rastreio_html = fields.Html(string='Rastreabilidade', compute='_compute_rastreio_html', sanitize=False)

    @api.depends('reclamacao_id')
    def _compute_rastreio_escolha(self):
        for rec in self:
            rec.rastreio_linha_id = rec.reclamacao_id.linha_ids[:1]
            rec.rastreio_consultar = False

    def _inverse_rastreio(self):
        pass  # escolha só de ecrã: não se grava

    @api.depends('rastreio_linha_id', 'rastreio_consultar')
    def _compute_rastreio_html(self):
        qweb = self.env['ir.qweb']
        for rec in self:
            linha = rec.rastreio_linha_id
            if not rec.rastreio_consultar or not linha:
                rec.rastreio_html = False
                continue
            try:
                dados = self.env['qualidade.rastreabilidade'].consultar(linha.codigo_artigo, linha.lote)
            except UserError as erro:
                rec.rastreio_html = qweb._render('qualidade_reclamacoes.rastreio_erro', {'mensagem': erro.args[0]})
                continue
            except Exception:
                _logger.exception("Rastreabilidade: erro ao consultar o Primavera (%s / %s)", linha.codigo_artigo, linha.lote)
                rec.rastreio_html = qweb._render('qualidade_reclamacoes.rastreio_erro', {
                    'mensagem': "O Primavera não respondeu a tempo. Tente de novo dentro de momentos."})
                continue
            rec.rastreio_html = qweb._render('qualidade_reclamacoes.rastreio_resultado', {
                'r': dados, 'url_material': self._url_material, 'fmt': self._fmt})

    @staticmethod
    def _url_material(artigo, lote):
        return '/qualidade/rastreabilidade/material?' + urlencode({'artigo': artigo, 'lote': lote})

    @staticmethod
    def _fmt(valor):
        """Datas dd/mm/aaaa e quantidades sem casas decimais desnecessárias."""
        if hasattr(valor, 'strftime'):
            return valor.strftime('%d/%m/%Y')
        if isinstance(valor, float):
            return ('%.3f' % valor).rstrip('0').rstrip('.').replace('.', ',')
        return valor or ''
