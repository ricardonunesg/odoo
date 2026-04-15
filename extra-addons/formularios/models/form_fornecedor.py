from odoo import models, fields, api
from odoo.exceptions import ValidationError
import base64

EMAILS_FIXOS = [
    'Carmo.cordeiro@mirazeite.com',
    'Bruno.simoes@mirazeite.com',
    'Ricardo.machado@mirazeite.com',
    'Rita.faroleira@mirazeite.com',
   'goncalo.simoes@mirazeite.com',
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

    fornecedor = fields.Char(string='Fornecedor', required=True)
    codigo_artigo = fields.Char(string='Código Artigo (Primavera)', required=True)
    descricao_artigo = fields.Char(string='Descrição Artigo (Primavera)', required=True)
    lote_guia_fatura = fields.Char(string='Lote / Guia remessa / Fatura', required=True)

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

    def _get_destinatarios_email(self):
        emails = set(EMAILS_FIXOS)
        if self.user_id and self.user_id.email:
            emails.add(self.user_id.email.strip())
        return ','.join(sorted([e for e in emails if e]))

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

        body = f'''
            <p>Foi criado um novo formulário de reclamação de fornecedor.</p>
            <p><strong>Utilizador:</strong> {self.user_id.name or ''}</p>
            <p><strong>Armazém:</strong> {dict(self._fields['armazem'].selection).get(self.armazem, '')}</p>
            <p><strong>Fornecedor:</strong> {self.fornecedor or ''}</p>
            <p><strong>Código Artigo:</strong> {self.codigo_artigo or ''}</p>
            <p><strong>Descrição Artigo:</strong> {self.descricao_artigo or ''}</p>
            <p><strong>Lote / Guia remessa / Fatura:</strong> {self.lote_guia_fatura or ''}</p>
            <p><strong>Descrição da Reclamação:</strong><br/>{self.descricao_reclamacao or ''}</p>
            <p><strong>Ações de Correção:</strong><br/>{self.acoes_correcao or ''}</p>
        '''

        mail = self.env['mail.mail'].sudo().create({
            'subject': f'Nova Reclamação de Fornecedor - {self.fornecedor or ""}',
            'email_from': 'noreply@mirazeite.com',
            'email_to': self._get_destinatarios_email(),
            'body_html': body,
            'attachment_ids': [(4, attachment.id)],
        })
        mail.sudo().send()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec._enviar_email_notificacao()
        return records


    def action_imprimir_pdf(self):
        self.ensure_one()
        return self.env.ref('formularios.action_report_form_fornecedor').report_action(self)
