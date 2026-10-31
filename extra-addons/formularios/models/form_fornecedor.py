from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError, AccessError

from .constantes import EMAILS_FIXOS, INSTALACOES  # noqa: F401 (mantidos para quem os importava daqui)


class FormReclamacaoFornecedor(models.Model):
    _name = 'form.reclama.fornecedor'
    _inherit = ['formularios.reclamacao.base']
    _description = 'Formulário - Reclamações de Fornecedor'
    _rec_name = 'fornecedor'
    _rec_names_search = ['name', 'numeros_anteriores', 'fornecedor']
    _campos_numeracao = ('name', 'numeros_anteriores', 'historico_numeracao')

    _campo_parceiro = 'fornecedor_partner_id'
    _campo_nome = 'fornecedor'
    _campo_lote = 'lote_guia_fatura'
    _titulo_lote = 'Lote / Guia / Fatura'
    _modelo_linha = 'form.reclama.fornecedor.linha'
    _relatorio = 'formularios.action_report_form_fornecedor'
    _prefixo_pdf = 'Formulario_Fornecedor'

    tipo_reclamacao = fields.Selection([
        ('externa', 'Externa'),
        ('interna', 'Interna'),
    ], string='Tipo', required=True, default='externa',
       help='Externa: reclamação a um fornecedor do Primavera. '
            'Interna: reclamação a outra instalação da Mirazeite.')
    instalacao_reclamada = fields.Selection(INSTALACOES, string='Instalação Reclamada')

    # Rastreabilidade da correcção de tipo (botão "Corrigir tipo", só administradores)
    numeros_anteriores = fields.Char(string='Números anteriores', readonly=True, copy=False, index=True,
                                     help='Números que a reclamação teve antes de uma correcção de tipo (pesquisáveis).')
    historico_numeracao = fields.Text(string='Histórico de numeração', readonly=True, copy=False)

    fornecedor_partner_id = fields.Many2one(
        'res.partner',
        string='Fornecedor ERP',
        domain="[('primavera_supplier_code', '!=', False)]",
    )
    fornecedor = fields.Char(string='Fornecedor', required=True)
    lote_guia_fatura = fields.Char(string='Lote / Guia remessa / Fatura (legado)')

    # Múltiplos artigos por reclamação
    linha_ids = fields.One2many(
        'form.reclama.fornecedor.linha', 'form_id',
        string='Artigos',
    )

    anexos_ids = fields.Many2many(
        'ir.attachment',
        'form_reclama_fornecedor_attachment_rel',
        'form_id', 'attachment_id',
        string='Documento da Reclamação',
        help='Email do fornecedor, whatsapp, documentos enviados pelo fornecedor, fotos, etc.'
    )

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

    def _prepare_partner_names(self, vals_list):
        for vals in vals_list:
            if vals.get('tipo_reclamacao') == 'interna':
                # Interna: sem fornecedor ERP; o nome vem da instalação reclamada
                vals['fornecedor_partner_id'] = False
                vals['fornecedor'] = self._nome_instalacao(vals.get('instalacao_reclamada'))
        return super()._prepare_partner_names(vals_list)

    @api.depends('name', 'fornecedor')
    def _compute_display_name(self):
        self._nome_com_numero()

    def _codigo_numeracao(self, vals):
        if vals.get('tipo_reclamacao') == 'interna':
            return 'formularios.reclamacao.interna'
        return 'formularios.reclamacao.fornecedor'

    def _textos_email(self):
        if self.tipo_reclamacao == 'interna':
            return (
                'Foi criado um novo formulário de reclamação interna.',
                f"<strong>Instalação Reclamada:</strong> {dict(INSTALACOES).get(self.instalacao_reclamada, '')}",
                f'Nova Reclamação Interna - {self.name} - {dict(INSTALACOES).get(self.instalacao_reclamada, "")}',
            )
        return (
            'Foi criado um novo formulário de reclamação de fornecedor.',
            f"<strong>Fornecedor:</strong> {self.fornecedor or ''}",
            f'Nova Reclamação de Fornecedor - {self.name} - {self.fornecedor or ""}',
        )

    def action_corrigir_tipo(self):
        """Botão "Corrigir tipo": abre a janela de confirmação (só administradores)."""
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise AccessError("Só os administradores podem corrigir o tipo de uma reclamação.")
        return {
            'type': 'ir.actions.act_window',
            'name': 'Corrigir tipo da reclamação',
            'res_model': 'formularios.corrigir.tipo',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_reclamacao_id': self.id},
        }

    def _corrigir_tipo(self, novo_tipo, motivo, instalacao=False, parceiro=False):
        """Muda Externa <-> Interna numa só operação: novo número da série certa (ano da reclamação
        original), número antigo guardado em numeros_anteriores e linha no histórico. Se algo falhar,
        a transacção é desfeita por inteiro (incluindo o contador da série)."""
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise AccessError("Só os administradores podem corrigir o tipo de uma reclamação.")
        motivo = (motivo or '').strip()
        if not motivo:
            raise UserError("Indique o motivo da correcção.")
        if novo_tipo not in ('externa', 'interna'):
            raise UserError("Tipo inválido.")
        if novo_tipo == 'interna' and not instalacao:
            raise UserError("Indique a 'Instalação Reclamada'.")
        if novo_tipo == 'externa' and not parceiro:
            raise UserError("Indique o 'Fornecedor ERP'.")
        # bloqueia a reclamação: duas correcções ao mesmo tempo esperam uma pela outra
        self.env.cr.execute('SELECT id FROM form_reclama_fornecedor WHERE id = %s FOR UPDATE', [self.id])
        self.invalidate_recordset()
        if novo_tipo == self.tipo_reclamacao:
            raise UserError("A reclamação %s já é do tipo escolhido." % self.name)
        tipos = dict(self._fields['tipo_reclamacao'].selection)
        antigo = self.name
        data_original = fields.Date.context_today(self, self.create_date)
        novo = self._proximo_numero(self._codigo_numeracao({'tipo_reclamacao': novo_tipo}), data_original)
        quando = fields.Datetime.context_timestamp(self, fields.Datetime.now()).strftime('%d/%m/%Y %H:%M')
        linha = '%s — %s → %s — %s → %s — %s — Motivo: %s' % (
            quando, antigo, novo, tipos[self.tipo_reclamacao], tipos[novo_tipo], self.env.user.name, motivo)
        vals = {
            'tipo_reclamacao': novo_tipo,
            'name': novo,
            'numeros_anteriores': ', '.join(n for n in (self.numeros_anteriores, antigo) if n),
            'historico_numeracao': '\n'.join(h for h in (self.historico_numeracao, linha) if h),
        }
        if novo_tipo == 'interna':
            vals['instalacao_reclamada'] = instalacao
        else:
            vals.update({'instalacao_reclamada': False, 'fornecedor_partner_id': parceiro.id, 'fornecedor': parceiro.display_name})
        self.with_context(formularios_numeracao=True).write(vals)
        return novo

    def write(self, vals):
        if 'tipo_reclamacao' in vals and not self.env.context.get('formularios_numeracao') \
                and any(rec.tipo_reclamacao != vals['tipo_reclamacao'] for rec in self):
            raise UserError("O tipo de uma reclamação gravada só pode ser corrigido por um administrador, "
                            "no botão 'Corrigir tipo'.")
        res = super().write(vals)
        if {'tipo_reclamacao', 'instalacao_reclamada'} & set(vals):
            for rec in self.filtered(lambda r: r.tipo_reclamacao == 'interna'):
                nome = rec._nome_instalacao(rec.instalacao_reclamada)
                if rec.fornecedor != nome or rec.fornecedor_partner_id:
                    super(FormReclamacaoFornecedor, rec).write({
                        'fornecedor': nome,
                        'fornecedor_partner_id': False,
                    })
        return res
