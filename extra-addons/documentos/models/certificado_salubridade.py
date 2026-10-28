from odoo import api, fields, models


class CertificadoSalubridadeTemplate(models.Model):
    _name  = 'certificado.salubridade.template'
    _description = 'Modelo de Certificado de Salubridade'
    _rec_name = 'name'
    _order = 'sequence, name'

    name      = fields.Char('Nome', required=True)
    sequence  = fields.Integer(default=10)
    active    = fields.Boolean(default=True)
    preset_id = fields.Many2one('certificado.organoletica.preset', 'Preset organoléticas padrão')
    default_morada_id = fields.Many2one('documento.morada', 'Morada padrão')
    local_assinatura_padrao = fields.Char('Local assinatura padrão', default='Lisboa')
    default_apreciacao = fields.Char('Apreciação padrão', default='Normal quanto às determinações efectuadas.')

    # Cabeçalho
    show_importador     = fields.Boolean('Importador',          default=True)
    show_distribuidor   = fields.Boolean('Distribuidor',        default=False)
    show_morada_cliente = fields.Boolean('Morada do importador',default=True)
    show_cnpj           = fields.Boolean('CNPJ / Tax ID',       default=True)
    show_orderer        = fields.Boolean('Orderer',             default=False)
    show_morada_orderer = fields.Boolean('Morada do Orderer',   default=False)

    # Corpo
    show_produto            = fields.Boolean('Produto / Tipo',          default=True)
    show_descricao_produtos = fields.Boolean('Descrição de produtos',   default=True)
    show_total_caixas       = fields.Boolean('Total de caixas',         default=True)
    show_peso_liquido       = fields.Boolean('P.L. (Peso líquido)',     default=True)
    show_organoleticas      = fields.Boolean('Organoléticas',           default=True)
    show_apreciacao         = fields.Boolean('Apreciação / Conclusion', default=True)
    show_data_embalamento   = fields.Boolean('Data de embalamento',     default=True)

    # Rodapé
    show_tabela_identificacao = fields.Boolean('Tabela de identificação', default=True)
    show_modo_transporte      = fields.Boolean('Modo de transporte',       default=True)
    show_fatura               = fields.Boolean('Fatura n.º',              default=True)
    show_data                 = fields.Boolean('Data',                     default=True)
    show_observacoes          = fields.Boolean('Observações',              default=False)

    # Outros
    in_english = fields.Boolean('Relatório em Inglês', default=False)


class CertificadoSalubridade(models.Model):
    _name    = 'certificado.salubridade'
    _description = 'Certificado de Salubridade'
    _inherit = 'certificado.narrativo.abstract'
    _rec_name = 'name'
    _order   = 'id desc'

    modelo_id = fields.Many2one('certificado.salubridade.template', 'Modelo', required=True)
    organoletica_ids = fields.One2many(
        'certificado.organoletica.linha', 'salubridade_id', 'Organoléticas',
    )

    def _get_sequence_code(self):
        return 'certificado.salubridade'

    def _get_report_xmlid(self):
        return 'documentos.action_report_certificado_salubridade'

    def _organoletica_fk_field(self):
        return 'salubridade_id'

    def _aplicar_preset_organoleticas(self):
        """Copia as linhas do preset para o documento se ainda não existirem."""
        for rec in self:
            if rec.modelo_id and rec.modelo_id.preset_id and not rec.organoletica_ids:
                vals = [
                    (0, 0, {
                        'salubridade_id': rec.id,
                        'sequence':       pl.sequence,
                        'caracteristica': pl.caracteristica,
                        'valor':          pl.valor,
                    })
                    for pl in rec.modelo_id.preset_id.linha_ids
                ]
                if vals:
                    rec.write({'organoletica_ids': vals})

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._aplicar_preset_organoleticas()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'modelo_id' in vals:
            self._aplicar_preset_organoleticas()
        return res

    # ── Mapeamento prefixo de lote → tipo de produto ─────────────────────────

    _LOTE_TIPO = {
        'LAV':  ('Azeite Virgem Extra',        'Extra Virgin Olive Oil'),
        'LAC':  ('Azeite',                     'Olive Oil'),
        'LTP':  ('Tempero Alimentar',          'Food Seasoning'),
        'LTPT': ('Tempero Alimentar',          'Food Seasoning'),
        'LOG':  ('Azeite de Bagaço (Pomace)',  'Pomace Olive Oil'),
        'LOGT': ('Azeite de Bagaço (Pomace)',  'Pomace Olive Oil'),
    }

    @staticmethod
    def _prefixo_lote(lote_str):
        """Extrai o prefixo de 3 letras do código de lote (ex: 'LAV43/26' → 'LAV')."""
        if not lote_str:
            return 'OUTRO'
        import re as _re
        m = _re.match(r'^([A-Za-z]{2,4})', lote_str.strip())
        return m.group(1).upper() if m else 'OUTRO'

    def action_carregar_linhas_fatura(self):
        """Agrupa linhas da fatura por tipo de produto e cria 1 certificado por tipo."""
        self.ensure_one()
        if not self.fatura_id:
            return

        fatura  = self.fatura_id
        partner = fatura.partner_id

        # ── Dados comuns de cabeçalho ────────────────────────────────────────
        cabecalho = {}
        cabecalho['fatura_ref']  = fatura.primavera_ref or fatura.name
        cabecalho['importador']  = fatura.importador or partner.name or self.importador
        cabecalho['distribuidor'] = fatura.distribuidor or self.distribuidor
        cabecalho['destino']     = (
            fatura.pais_destino_id.name if fatura.pais_destino_id
            else fatura.destino or self.destino
        )
        cabecalho['fatura_id']   = fatura.id
        if partner:
            parts = [p for p in [
                partner.street, partner.street2,
                partner.zip, partner.city,
                partner.country_id.name,
            ] if p]
            cabecalho['morada_cliente'] = '\n'.join(parts)
            cabecalho['cnpj_cliente']   = self._formatar_cnpj(partner.vat)

        # ── Linhas de produto da fatura (excluir paletes e transporte) ──────────
        inv_lines = fatura.invoice_line_ids.filtered(
            lambda l: l.display_type == 'product'
            and l.product_id
            and l.product_id.default_code
            and not (l.product_id.default_code or '').upper().startswith('PAL')
        )
        if not inv_lines:
            return {"type": "ir.actions.client", "tag": "reload"}

        liquido = inv_lines._peso_liquido_unit()

        # ── Agrupar por prefixo de lote — só prefixos reconhecidos ──────────
        grupos = {}
        for l in inv_lines:
            lote = l.lote or ''
            if lote.startswith('<') and lote.endswith('>'):
                lote = ''
            prefixo = self._prefixo_lote(lote)
            # Ignorar linhas sem prefixo reconhecido (paletes, transporte, etc.)
            if prefixo not in self._LOTE_TIPO:
                continue
            grupos.setdefault(prefixo, []).append(l)

        prefixos = sorted(grupos.keys())   # ex: ['LAC', 'LAV']

        # ── Preencher o certificado actual com o 1º grupo ────────────────────
        todos_ids = [self.id]

        def _preencher(cert, prefixo, linhas):
            tipo_pt, tipo_en = self._LOTE_TIPO.get(prefixo, (prefixo, prefixo))
            tipo = tipo_en if cert.modelo_id.in_english else tipo_pt

            lotes_unicos = []
            for l in linhas:
                lt = l.lote or ''
                if lt.startswith('<') and lt.endswith('>'):
                    lt = ''
                if lt and lt not in lotes_unicos:
                    lotes_unicos.append(lt)

            total_cx = sum(l.caixas or int(l.quantity) for l in linhas)
            total_pl = sum(
                (l.caixas or int(l.quantity)) * liquido[l.id]
                for l in linhas
            )

            visto = {}
            for l in linhas:
                pname = l.product_id.name or ''
                cx = l.caixas or int(l.quantity)
                visto[pname] = visto.get(pname, 0) + cx
            desc_lines = []
            for pname, cx in visto.items():
                marca = self._extrair_marca(pname)
                resto = pname[len(marca):].strip() if marca else pname
                desc_lines.append(f"{(marca + ' ') if marca else ''}{resto} – {cx} boxes")

            first = linhas[0]
            fab = first.product_id.x_data_fabricacao
            val = first.data_validade or first.product_id.x_data_validade

            write_vals = dict(cabecalho)
            write_vals.update({
                'tipo_produto':       tipo,
                'lotes_descricao':    ', '.join(lotes_unicos),
                'total_caixas':       total_cx,
                'peso_liquido_total': total_pl,
                'descricao_produtos': '\n'.join(desc_lines),
                'data_embalamento':   f"{fab.month:02d}/{fab.year}" if fab else cert.data_embalamento,
                'data_validade':      f"{val.month:02d}/{val.year}" if val else cert.data_validade,
            })
            cert.write(write_vals)
            # Aplicar preset organoléticas se não houver
            cert._aplicar_preset_organoleticas()

        # Gerar número para o certificado actual se ainda for 'Novo'
        if self.name == 'Novo':
            self.name = (
                self.env['ir.sequence'].next_by_code('certificado.salubridade') or 'Novo'
            )

        # Preencher certificado actual com 1º prefixo
        _preencher(self, prefixos[0], grupos[prefixos[0]])

        # ── Criar novos certificados para prefixos adicionais ────────────────
        for prefixo in prefixos[1:]:
            seq = self.env['ir.sequence'].next_by_code('certificado.salubridade') or 'Novo'
            novo = self.create({
                'name':       seq,
                'modelo_id':  self.modelo_id.id,
                'date':       self.date,
                'fatura_id':  fatura.id,
                'morada_id':  self.morada_id.id if self.morada_id else False,
                'local_assinatura': self.local_assinatura,
                'apreciacao': self.apreciacao,
            })
            _preencher(novo, prefixo, grupos[prefixo])
            todos_ids.append(novo.id)

        # ── Abrir todos os certificados criados ──────────────────────────────
        if len(todos_ids) == 1:
            return {"type": "ir.actions.client", "tag": "reload"}

        return {
            'type':      'ir.actions.act_window',
            'name':      f'Certificados — {fatura.primavera_ref or fatura.name}',
            'res_model': 'certificado.salubridade',
            'view_mode': 'list,form',
            'domain':    [('id', 'in', todos_ids)],
            'target':    'current',
        }
