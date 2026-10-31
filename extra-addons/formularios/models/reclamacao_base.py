from odoo import models, fields, api
from odoo.exceptions import ValidationError
import base64

from .constantes import EMAILS_FIXOS, ARMAZENS


class ReclamacaoBase(models.AbstractModel):
    """Parte comum às reclamações de cliente e de fornecedor.

    Não tem tabela própria: os campos e o comportamento passam para
    form.reclama.cliente e form.reclama.fornecedor. Cada um indica as suas
    diferenças nos atributos abaixo e em _textos_email().
    """
    _name = 'formularios.reclamacao.base'
    _description = 'Base comum das Reclamações (Formulários)'

    _campo_parceiro = None      # 'cliente_partner_id' / 'fornecedor_partner_id'
    _campo_nome = None          # 'cliente' / 'fornecedor'
    _campo_lote = None          # 'lote' / 'lote_guia_fatura' (no cabeçalho legado e nas linhas)
    _titulo_lote = None         # coluna do lote na tabela do email
    _modelo_linha = None        # 'form.reclama.cliente.linha' / 'form.reclama.fornecedor.linha'
    _relatorio = None           # xmlid do relatório PDF
    _prefixo_pdf = None         # 'Formulario_Cliente' / 'Formulario_Fornecedor'

    user_id = fields.Many2one('res.users', string='Utilizador', required=True)
    armazem = fields.Selection(ARMAZENS, string='Armazém', required=True)

    # Campos legados de artigo único — mantidos para compatibilidade, mas não obrigatórios
    artigo_id = fields.Many2one(
        'product.template',
        string='Artigo ERP (legado)',
        domain="[('primavera_code', '!=', False)]",
    )
    codigo_artigo = fields.Char(string='Código Artigo (legado)')
    descricao_artigo = fields.Char(string='Descrição Artigo (legado)')

    descricao_reclamacao = fields.Text(string='Descrição da Reclamação', required=True)
    acoes_correcao = fields.Text(string='Ações de Correção')

    @api.constrains('anexos_ids')
    def _check_anexos_obrigatorio(self):
        for rec in self:
            if not rec.anexos_ids:
                raise ValidationError("É obrigatório anexar pelo menos 1 ficheiro no 'Documento da Reclamação'.")

    @api.constrains('linha_ids')
    def _check_pelo_menos_um_artigo(self):
        for rec in self:
            if not rec.linha_ids:
                raise ValidationError("É obrigatório adicionar pelo menos 1 artigo à reclamação.")

    def _vincular_anexos_ao_registo(self):
        for rec in self:
            rec.anexos_ids.sudo().write({
                'res_model': rec._name,
                'res_id': rec.id,
            })

    def _get_destinatarios_email(self):
        emails = set(EMAILS_FIXOS)
        if self.user_id and self.user_id.email:
            emails.add(self.user_id.email.strip())
        return ','.join(sorted([e for e in emails if e]))

    @api.onchange('artigo_id')
    def _onchange_artigo_id(self):
        for rec in self:
            rec.codigo_artigo = rec.artigo_id.primavera_code or rec.artigo_id.default_code or False
            rec.descricao_artigo = rec.artigo_id.name or False

    def _prepare_partner_names(self, vals_list):
        partner_ids = [vals.get(self._campo_parceiro) for vals in vals_list if vals.get(self._campo_parceiro)]
        partners_by_id = {
            partner.id: partner.display_name
            for partner in self.env['res.partner'].browse(partner_ids).exists()
        }
        for vals in vals_list:
            partner_id = vals.get(self._campo_parceiro)
            if partner_id and not vals.get(self._campo_nome):
                vals[self._campo_nome] = partners_by_id.get(partner_id)
        return vals_list

    def _prepare_product_values(self, vals_list):
        product_ids = [vals.get('artigo_id') for vals in vals_list if vals.get('artigo_id')]
        products_by_id = {
            product.id: product
            for product in self.env['product.template'].browse(product_ids).exists()
        }
        for vals in vals_list:
            product = products_by_id.get(vals.get('artigo_id'))
            if not product:
                continue
            if not vals.get('codigo_artigo'):
                vals['codigo_artigo'] = product.primavera_code or product.default_code
            if not vals.get('descricao_artigo'):
                vals['descricao_artigo'] = product.name
        return vals_list

    def _textos_email(self):
        """Devolve (introdução, linha da entidade, assunto) do email de nova reclamação."""
        raise NotImplementedError

    def _enviar_email_notificacao(self):
        self.ensure_one()

        report = self.env.ref(self._relatorio)
        pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf(
            self._relatorio,
            [self.id]
        )

        attachment = self.env['ir.attachment'].sudo().create({
            'name': f'{self._prefixo_pdf}_{self.id}.pdf',
            'type': 'binary',
            'datas': base64.b64encode(pdf_content),
            'mimetype': 'application/pdf',
            'res_model': self._name,
            'res_id': self.id,
        })

        linhas_html = ''
        if self.linha_ids:
            linhas_html = f'<table border="1" cellspacing="0" cellpadding="4" style="border-collapse:collapse"><tr><th>Código</th><th>Descrição</th><th>{self._titulo_lote}</th></tr>'
            for l in self.linha_ids:
                linhas_html += (
                    f'<tr><td>{l.codigo_artigo or ""}</td>'
                    f'<td>{l.descricao_artigo or ""}</td>'
                    f'<td>{l[self._campo_lote] or ""}</td></tr>'
                )
            linhas_html += '</table>'
        intro, entidade, assunto = self._textos_email()
        body = f'''
            <p>{intro}</p>
            <p><strong>Utilizador:</strong> {self.user_id.name or ''}</p>
            <p><strong>Armazém:</strong> {dict(self._fields['armazem'].selection).get(self.armazem, '')}</p>
            <p>{entidade}</p>
            <p><strong>Artigos:</strong></p>
            {linhas_html}
            <p><strong>Descrição da Reclamação:</strong><br/>{self.descricao_reclamacao or ''}</p>
            <p><strong>Ações de Correção:</strong><br/>{self.acoes_correcao or ''}</p>
        '''

        # Anexar PDF + ficheiros enviados pelo utilizador (anexos_ids)
        attach_ids = [(4, attachment.id)]
        for a in self.anexos_ids:
            attach_ids.append((4, a.id))

        mail = self.env['mail.mail'].sudo().create({
            'subject': assunto,
            'email_from': 'noreply@mirazeite.com',
            'email_to': self._get_destinatarios_email(),
            'body_html': body,
            'attachment_ids': attach_ids,
        })
        mail.sudo().send()

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = self._prepare_partner_names(vals_list)
        vals_list = self._prepare_product_values(vals_list)
        records = super().create(vals_list)
        Linha = self.env[self._modelo_linha]
        for rec in records:
            # Backward compat: se foi criada sem linhas mas com campos antigos preenchidos,
            # criar automaticamente 1 linha a partir desses campos
            if not rec.linha_ids and rec.codigo_artigo:
                Linha.create({
                    'form_id': rec.id,
                    'artigo_id': rec.artigo_id.id if rec.artigo_id else False,
                    'codigo_artigo': rec.codigo_artigo,
                    'descricao_artigo': rec.descricao_artigo or rec.codigo_artigo,
                    self._campo_lote: rec[self._campo_lote] or '-',
                })
            rec._vincular_anexos_ao_registo()
            rec._enviar_email_notificacao()
        return records

    def write(self, vals):
        if vals.get(self._campo_parceiro) and not vals.get(self._campo_nome):
            partner = self.env['res.partner'].browse(vals[self._campo_parceiro]).exists()
            if partner:
                vals = dict(vals, **{self._campo_nome: partner.display_name})
        if vals.get('artigo_id') and (
            not vals.get('codigo_artigo') or not vals.get('descricao_artigo')
        ):
            product = self.env['product.template'].browse(vals['artigo_id']).exists()
            if product:
                vals = dict(vals)
                vals.setdefault('codigo_artigo', product.primavera_code or product.default_code)
                vals.setdefault('descricao_artigo', product.name)
        res = super().write(vals)
        if 'anexos_ids' in vals:
            self._vincular_anexos_ao_registo()
        return res

    def action_imprimir_pdf(self):
        self.ensure_one()
        return self.env.ref(self._relatorio).report_action(self)
