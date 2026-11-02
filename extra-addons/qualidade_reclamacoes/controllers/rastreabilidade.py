from odoo import http
from odoo.exceptions import UserError
from odoo.http import request

from ..models.resposta_cliente import QualidadeRespostaCliente


class QualidadeRastreabilidadeController(http.Controller):

    @http.route('/qualidade/rastreabilidade/material', type='http', auth='user', methods=['GET'])
    def outros_produtos(self, artigo='', lote='', **_kw):
        """Outros produtos acabados que usaram um lote de material (só leitura do Primavera; só Qualidade)."""
        user = request.env.user
        if not (user.has_group('qualidade_reclamacoes.group_qualidade_eng') or user.has_group('base.group_system')):
            return request.not_found()
        try:
            dados = request.env['qualidade.rastreabilidade'].outros_produtos(artigo, lote)
        except UserError as erro:
            dados = {'artigo': artigo, 'lote': lote, 'descricao': '', 'produtos': [], 'avisos': [erro.args[0]]}
        return request.render('qualidade_reclamacoes.rastreio_material_pagina', {
            'r': dados, 'fmt': QualidadeRespostaCliente._fmt})
