from odoo import api, fields, models

# Logins dos seguidores automáticos de todas as ECLs
_ECL_FOLLOWER_LOGINS = [
    'adriana.filipa@mirazeite.com',
    'bruno.simoes@mirazeite.com',
    'goncalo.simoes@mirazeite.com',
    'itmirazeite@gmail.com',
    'rita.faroleira@mirazeite.com',
    'ricardo.machado@mirazeite.com',
    'carmo.cordeiro@mirazeite.com',
    'claudia.zacarias@mirazeite.com',
    'alexandre.simoes@mirazeite.com',
]


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # ── Identificação Primavera ─────────────────────────────────────────
    primavera_ecl_ref = fields.Char('Ref. ECL Primavera', index=True, copy=False, readonly=True)
    export_doc_type = fields.Selection([
        ('standard', 'Documentação Standard'),
        ('additional', 'Documentação Adicional'),
    ], string='Tipo Documentação')

    # ── Card manual (criado directamente no Kanban) ─────────────────────
    manual_card = fields.Boolean(
        'Card Manual', default=False, copy=False, index=True,
        help="Quando True, este registo foi criado manualmente no Kanban e "
             "não tem origem no Primavera. Não é tocado pelos crons de sincronização.",
    )

    # ── Campos de exportação ────────────────────────────────────────────
    ecl_incoterm     = fields.Char('Incoterm')
    ecl_incoterm_local = fields.Char('Local/Porto Incoterm')
    ecl_pais_destino_id = fields.Many2one('res.country', 'País Destino')
    ecl_transitario  = fields.Char('Transitário')

    # ── Stage (kanban) ──────────────────────────────────────────────────
    stage_id = fields.Many2one(
        'export.ecl.stage', 'Stage',
        default=lambda self: self.env['export.ecl.stage'].search([], order='sequence', limit=1),
        group_expand='_read_group_stage_ids',
        ondelete='restrict',
        index=True,
    )
    stage_fold = fields.Boolean(related='stage_id.fold', store=False)
    color      = fields.Integer(related='stage_id.color', store=True, readonly=True)

    # ── Campos related do parceiro ──────────────────────────────────────
    partner_ref = fields.Char(
        'Nº Cliente Primavera', related='partner_id.ref', store=True, readonly=True,
    )
    assignee_id = fields.Many2one(
        'res.users', 'Assignee',
        related='partner_id.user_id', store=True, readonly=True,
    )

    # ── Documentos de exportação ────────────────────────────────────────
    ecl_doc_line_ids = fields.One2many(
        'export.ecl.document.line', 'sale_order_id', 'Documentos',
    )
    primavera_fatura_refs = fields.Char('Fatura(s) Primavera', readonly=True)

    # ── DMS ──────────────────────────────────────────────────────────────
    ecl_dms_directory_id = fields.Many2one(
        'dms.directory', 'Pasta DMS', copy=False, ondelete='set null',
    )
    dms_file_count = fields.Integer(compute='_compute_dms_file_count', string='Ficheiros DMS')

    @api.depends('ecl_dms_directory_id')
    def _compute_dms_file_count(self):
        for rec in self:
            if rec.ecl_dms_directory_id:
                rec.dms_file_count = self.env['dms.file'].sudo().search_count(
                    [('directory_id', '=', rec.ecl_dms_directory_id.id)]
                )
            else:
                rec.dms_file_count = 0

    def _dms_root_dir(self):
        """Devolve o directório raiz 'Processos Exportação (Histórico)'."""
        return self.env['dms.directory'].sudo().search(
            [('is_root_directory', '=', True),
             ('name', '=', 'Processos Exportação (Histórico)')],
            limit=1,
        )

    def _get_or_create_dms_dir(self, name, parent_id, res_model=None, res_id=None):
        Dir = self.env['dms.directory'].sudo()
        d = Dir.search([('name', '=', name), ('parent_id', '=', parent_id)], limit=1)
        if not d:
            vals = {'name': name, 'parent_id': parent_id}
            if res_model and res_id:
                vals.update({'res_model': res_model, 'res_id': res_id})
            d = Dir.with_context(check_name=False).create(vals)
        return d

    def action_create_dms_folder(self):
        """Cria (ou devolve) a pasta DMS para esta ECL."""
        for rec in self:
            if not rec.primavera_ecl_ref:
                continue
            root = rec._dms_root_dir()
            if not root:
                continue
            year = str(rec.date_order.year) if rec.date_order else '2026'
            year_dir = rec._get_or_create_dms_dir(year, root.id)
            partner = rec.partner_id
            if partner and partner.primavera_customer_code:
                cli_name = f"{partner.primavera_customer_code} - {partner.name}"
            elif partner:
                cli_name = partner.name or 'Desconhecido'
            else:
                continue
            cli_dir = rec._get_or_create_dms_dir(
                cli_name, year_dir.id, 'res.partner', partner.id,
            )
            ecl_dir = rec._get_or_create_dms_dir(
                rec.primavera_ecl_ref, cli_dir.id, 'sale.order', rec.id,
            )
            if rec.ecl_dms_directory_id != ecl_dir:
                rec.ecl_dms_directory_id = ecl_dir

    def action_open_dms_folder(self):
        self.ensure_one()
        if not self.ecl_dms_directory_id:
            self.action_create_dms_folder()
        if not self.ecl_dms_directory_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': self.primavera_ecl_ref or 'Pasta DMS',
            'res_model': 'dms.file',
            'view_mode': 'kanban,list,form',
            'domain': [('directory_id', '=', self.ecl_dms_directory_id.id)],
            'context': {'default_directory_id': self.ecl_dms_directory_id.id},
        }

    def _ecl_follower_partner_ids(self):
        """Devolve os partner_ids dos seguidores automáticos das ECLs."""
        users = self.env['res.users'].sudo().search(
            [('login', 'in', _ECL_FOLLOWER_LOGINS), ('active', '=', True)]
        )
        return users.mapped('partner_id').ids

    def _subscribe_ecl_followers(self):
        """Adiciona os seguidores automáticos a estas ECLs (sem duplicar)."""
        partner_ids = self._ecl_follower_partner_ids()
        if partner_ids:
            self.message_subscribe(partner_ids=partner_ids)

    @api.model_create_multi
    def create(self, vals_list):
        # Se o context vem das actions de exportação, garantir que manual_card=True
        ctx = self.env.context
        ctx_default_manual = ctx.get('default_manual_card')
        ctx_default_doctype = ctx.get('default_export_doc_type')
        if ctx_default_manual or ctx_default_doctype:
            for vals in vals_list:
                if not vals.get('primavera_ecl_ref'):
                    if ctx_default_manual and 'manual_card' not in vals:
                        vals['manual_card'] = True
                    if ctx_default_doctype and not vals.get('export_doc_type'):
                        vals['export_doc_type'] = ctx_default_doctype
        records = super().create(vals_list)
        for rec in records.filtered(lambda r: r.primavera_ecl_ref or r.manual_card):
            # Pasta DMS
            if not rec.ecl_dms_directory_id:
                try:
                    rec.action_create_dms_folder()
                except Exception:
                    pass
            # Seguidores automáticos — logo que a ECL entra no Kanban
            try:
                rec._subscribe_ecl_followers()
            except Exception:
                pass
        return records

    @api.onchange('partner_id', 'manual_card')
    def _onchange_partner_for_manual_card(self):
        """Quando se cria um card manual, popular automaticamente
        export_doc_type e documentos exigidos a partir do cliente."""
        for rec in self:
            if not rec.manual_card or not rec.partner_id:
                continue
            if not rec.export_doc_type and rec.partner_id.export_doc_type:
                rec.export_doc_type = rec.partner_id.export_doc_type
            if not rec.ecl_doc_line_ids and rec.partner_id.required_doc_ids:
                bl_type = self.env.ref(
                    'documentos.doc_type_bl', raise_if_not_found=False
                )
                assignee = rec.partner_id.user_id
                lines = []
                for doc in rec.partner_id.required_doc_ids.sorted('sequence'):
                    if bl_type and doc.id == bl_type.id and assignee:
                        responsible = [(6, 0, assignee.ids)]
                    else:
                        responsible = [(6, 0, doc.responsible_ids.ids)]
                    lines.append((0, 0, {
                        'doc_type_id': doc.id,
                        'responsible_ids': responsible,
                        'sequence': doc.sequence,
                    }))
                rec.ecl_doc_line_ids = lines

    def write(self, vals):
        res = super().write(vals)
        if 'primavera_ecl_ref' in vals:
            for rec in self.filtered(lambda r: r.primavera_ecl_ref):
                # Pasta DMS
                if not rec.ecl_dms_directory_id:
                    try:
                        rec.action_create_dms_folder()
                    except Exception:
                        pass
                # Seguidores automáticos
                try:
                    rec._subscribe_ecl_followers()
                except Exception:
                    pass
        return res

    task_count = fields.Integer(compute='_compute_task_count', string='Tasks')

    @api.depends('ecl_doc_line_ids.task_id')
    def _compute_task_count(self):
        for rec in self:
            rec.task_count = len(rec.ecl_doc_line_ids.filtered('task_id').task_id)

    def action_view_tasks(self):
        task_ids = self.ecl_doc_line_ids.task_id.ids
        return {
            'type': 'ir.actions.act_window',
            'name': 'Tasks — ' + (self.primavera_ecl_ref or self.name or ''),
            'res_model': 'project.task',
            'view_mode': 'list,form',
            'domain': [('id', 'in', task_ids)],
        }

    def action_resync_from_primavera(self):
        """Re-importa os dados desta ECL do Primavera, aplicando alterações feitas no ERP."""
        self.ensure_one()
        if not self.primavera_ecl_ref:
            return False
        conn = self.env['primavera.connection'].sudo().search(
            [('active', '=', True)], limit=1
        )
        if not conn:
            return False
        result = conn._resync_single_ecl(self.primavera_ecl_ref)
        message = (
            f"ECL {self.primavera_ecl_ref} re-sincronizada com sucesso."
            if result else
            f"Não foi possível sincronizar a ECL {self.primavera_ecl_ref} do Primavera."
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Sincronizar do Primavera',
                'message': message,
                'type': 'success' if result else 'warning',
                'sticky': False,
            },
        }

    ecl_doc_json = fields.Json(
        compute='_compute_ecl_doc_json',
        string='Docs Preview',
    )

    @api.depends('ecl_doc_line_ids.doc_type_id', 'ecl_doc_line_ids.state', 'ecl_doc_line_ids.sequence')
    def _compute_ecl_doc_json(self):
        for rec in self:
            lines = rec.ecl_doc_line_ids
            rec.ecl_doc_json = {
                'docs': [{'name': l.doc_type_id.name or '', 'state': l.state} for l in lines],
                'total': len(lines),
            }

    @api.model
    def _read_group_stage_ids(self, stages, domain):
        return stages.search([])


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # Campos preenchidos a partir do Primavera na sincronização da ECL
    lote           = fields.Char('Lote', copy=False)
    data_validade  = fields.Date('Validade', copy=False)
    peso_liquido   = fields.Float('P. Líquido Unit. (kg)', digits='Stock Weight', copy=False)
    peso_bruto     = fields.Float('P. Bruto Unit. (kg)',   digits='Stock Weight', copy=False)
    volume         = fields.Float('Volume Unit. (m³)',     digits='Volume', copy=False)
    caixas         = fields.Integer('Caixas', copy=False)
    unidades_linha = fields.Float('Unidades Totais', digits=(16, 2), copy=False)
