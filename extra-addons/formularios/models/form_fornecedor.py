from odoo import models, fields, api
from odoo.exceptions import ValidationError
import base64

EMAILS_FIXOS = [
    'Carmo.cordeiro@mirazeite.com',
    'Bruno.simoes@mirazeite.com',
    'Ricardo.machado@mirazeite.com',
    'Rita.faroleira@mirazeite.com',
    'goncalo.simoes@mirazeite.com',
    'pedro.santos@mirazeite.com',
    'ricardo.nunes@mirazeite.com',
]

# Instalações a que se pode fazer uma reclamação interna (ex.: Arruda reclama a Tomar)
INSTALACOES = [
    ('a1', 'A1 - Arruda'),
    ('a2', 'A2 - Tomar'),
]

class FormReclamacaoFornecedor(models.Model):
    _name = 'form.reclama.fornecedor'
    _description = 'Formulário - Reclamações de Fornecedor'
    _rec_name = 'fornecedor'

    user_id = fields.Many2one('res.users', string='Utilizador', required=True)
    armazem = fields.Selection([
        ('a1', 'A1 - Arruda'),
        ('a2', 'A2 - Tomar'),
        ('outra', 'Outra'),
    ], string='Armazém', required=True)

    tipo_reclamacao = fields.Selection([
        ('externa', 'Externa'),
        ('interna', 'Interna'),
    ], string='Tipo', required=True, default='externa',
       help='Externa: reclamação a um fornecedor do Primavera. '
            'Interna: reclamação a outra instalação da Mirazeite.')
    instalacao_reclamada = fields.Selection(INSTALACOES, string='Instalação Reclamada')

    fornecedor_partner_id = fields.Many2one(
        'res.partner',
        string='Fornecedor ERP',
        domain="[('primavera_supplier_code', '!=', False)]",
    )
    fornecedor = fields.Char(string='Fornecedor', required=True)
    # Campos legados de artigo único — mantidos para compatibilidade, mas não obrigatórios
    artigo_id = fields.Many2one(
        'product.template',
        string='Artigo ERP (legado)',
        domain="[('primavera_code', '!=', False)]",
    )
    codigo_artigo = fields.Char(string='Código Artigo (legado)')
    descricao_artigo = fields.Char(string='Descrição Artigo (legado)')
    lote_guia_fatura = fields.Char(string='Lote / Guia remessa / Fatura (legado)')

    # Múltiplos artigos por reclamação
    linha_ids = fields.One2many(
        'form.reclama.fornecedor.linha', 'form_id',
        string='Artigos',
    )

    descricao_reclamacao = fields.Text(string='Descrição da Reclamação', required=True)
    acoes_correcao = fields.Text(string='Ações de Correção')

    anexos_ids = fields.Many2many(
        'ir.attachment',
        'form_reclama_fornecedor_attachment_rel',
        'form_id', 'attachment_id',
        string='Documento da Reclamação',
        help='Email do fornecedor, whatsapp, documentos enviados pelo fornecedor, fotos, etc.'
    )

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

    @api.constrains('tipo_reclamacao', 'instalacao_reclamada', 'armazem')
    def _check_instalacao_reclamada(self):
        for rec in self:
            if rec.tipo_reclamacao != 'interna':
                continue
            if not rec.instalacao_reclamada:
                raise ValidationError("Numa reclamação interna é obrigatório indicar a 'Instalação Reclamada'.")
            if rec.instalacao_reclamada == rec.armazem:
                raise ValidationError("A 'Instalação Reclamada' não pode ser a mesma do 'Armazém' de origem.")

    @api.model
    def _nome_instalacao(self, instalacao):
        """Nome guardado em 'fornecedor' numa reclamação interna (listas, email, painéis)."""
        return 'Interna - %s' % (dict(INSTALACOES).get(instalacao) or '?')

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

    @api.onchange('fornecedor_partner_id')
    def _onchange_fornecedor_partner_id(self):
        for rec in self:
            rec.fornecedor = rec.fornecedor_partner_id.display_name or False

    @api.onchange('tipo_reclamacao', 'instalacao_reclamada')
    def _onchange_tipo_reclamacao(self):
        for rec in self:
            if rec.tipo_reclamacao == 'interna':
                rec.fornecedor_partner_id = False
                rec.fornecedor = rec._nome_instalacao(rec.instalacao_reclamada) if rec.instalacao_reclamada else False
            else:
                rec.instalacao_reclamada = False
                rec.fornecedor = rec.fornecedor_partner_id.display_name or False

    @api.onchange('artigo_id')
    def _onchange_artigo_id(self):
        for rec in self:
            rec.codigo_artigo = rec.artigo_id.primavera_code or rec.artigo_id.default_code or False
            rec.descricao_artigo = rec.artigo_id.name or False

    def _prepare_partner_names(self, vals_list):
        partner_ids = [vals.get('fornecedor_partner_id') for vals in vals_list if vals.get('fornecedor_partner_id')]
        partners_by_id = {
            partner.id: partner.display_name
            for partner in self.env['res.partner'].browse(partner_ids).exists()
        }
        for vals in vals_list:
            if vals.get('tipo_reclamacao') == 'interna':
                # Interna: sem fornecedor ERP; o nome vem da instalação reclamada
                vals['fornecedor_partner_id'] = False
                vals['fornecedor'] = self._nome_instalacao(vals.get('instalacao_reclamada'))
                continue
            partner_id = vals.get('fornecedor_partner_id')
            if partner_id and not vals.get('fornecedor'):
                vals['fornecedor'] = partners_by_id.get(partner_id)
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

    def _enviar_email_notificacao(self):
        self.ensure_one()

        report = self.env.ref('formularios.action_report_form_fornecedor')
        pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf(
            'formularios.action_report_form_fornecedor',
            [self.id]
        )

        attachment = self.env['ir.attachment'].sudo().create({
            'name': f'Formulario_Fornecedor_{self.id}.pdf',
            'type': 'binary',
            'datas': base64.b64encode(pdf_content),
            'mimetype': 'application/pdf',
            'res_model': self._name,
            'res_id': self.id,
        })

        linhas_html = ''
        if self.linha_ids:
            linhas_html = '<table border="1" cellspacing="0" cellpadding="4" style="border-collapse:collapse"><tr><th>Código</th><th>Descrição</th><th>Lote / Guia / Fatura</th></tr>'
            for l in self.linha_ids:
                linhas_html += (
                    f'<tr><td>{l.codigo_artigo or ""}</td>'
                    f'<td>{l.descricao_artigo or ""}</td>'
                    f'<td>{l.lote_guia_fatura or ""}</td></tr>'
                )
            linhas_html += '</table>'
        if self.tipo_reclamacao == 'interna':
            intro = 'Foi criado um novo formulário de reclamação interna.'
            entidade = f"<strong>Instalação Reclamada:</strong> {dict(INSTALACOES).get(self.instalacao_reclamada, '')}"
            assunto = f'Nova Reclamação Interna - {dict(INSTALACOES).get(self.instalacao_reclamada, "")}'
        else:
            intro = 'Foi criado um novo formulário de reclamação de fornecedor.'
            entidade = f"<strong>Fornecedor:</strong> {self.fornecedor or ''}"
            assunto = f'Nova Reclamação de Fornecedor - {self.fornecedor or ""}'
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
        Linha = self.env['form.reclama.fornecedor.linha']
        for rec in records:
            # Backward compat: criar linha automática se vier só com os campos antigos
            if not rec.linha_ids and rec.codigo_artigo:
                Linha.create({
                    'form_id': rec.id,
                    'artigo_id': rec.artigo_id.id if rec.artigo_id else False,
                    'codigo_artigo': rec.codigo_artigo,
                    'descricao_artigo': rec.descricao_artigo or rec.codigo_artigo,
                    'lote_guia_fatura': rec.lote_guia_fatura or '-',
                })
            rec._vincular_anexos_ao_registo()
            rec._enviar_email_notificacao()
        return records

    def write(self, vals):
        if vals.get('fornecedor_partner_id') and not vals.get('fornecedor'):
            partner = self.env['res.partner'].browse(vals['fornecedor_partner_id']).exists()
            if partner:
                vals = dict(vals, fornecedor=partner.display_name)
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
        if {'tipo_reclamacao', 'instalacao_reclamada'} & set(vals):
            for rec in self.filtered(lambda r: r.tipo_reclamacao == 'interna'):
                nome = rec._nome_instalacao(rec.instalacao_reclamada)
                if rec.fornecedor != nome or rec.fornecedor_partner_id:
                    super(FormReclamacaoFornecedor, rec).write({
                        'fornecedor': nome,
                        'fornecedor_partner_id': False,
                    })
        return res


    def action_imprimir_pdf(self):
        self.ensure_one()
        return self.env.ref('formularios.action_report_form_fornecedor').report_action(self)
