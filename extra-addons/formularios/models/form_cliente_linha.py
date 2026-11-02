from odoo import models, fields, api, _


class FormReclamacaoClienteLinha(models.Model):
    _name = 'form.reclama.cliente.linha'
    _description = 'Linha de Artigo - Reclamação de Cliente'
    _order = 'sequence, id'

    form_id = fields.Many2one(
        'form.reclama.cliente',
        string='Reclamação',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(default=10)

    artigo_id = fields.Many2one(
        'product.template',
        string='Artigo ERP',
        domain="[('primavera_code', '!=', False)]",
    )
    codigo_artigo = fields.Char(string='Código Artigo (Primavera)', required=True)
    descricao_artigo = fields.Char(string='Descrição Artigo (Primavera)', required=True)
    lote = fields.Char(string='Lote', required=True)

    @api.depends('descricao_artigo', 'codigo_artigo', 'lote')
    def _compute_display_name(self):
        # descrição do artigo (Primavera) — lote; o código continua a ser o que se usa nas consultas
        for rec in self:
            rec.display_name = ' — '.join(x for x in (rec.descricao_artigo or rec.codigo_artigo, rec.lote) if x) or _('Linha de artigo')

    @api.model
    def lotes_vendidos_primavera(self, codigo_artigo, partner_id):
        """Lotes do artigo faturados (FA/FAT/FRT, não anuladas) ao cliente, mais recentes primeiro. Só leitura.
        Usado pelo botão de lotes do campo Lote; o lote continua a poder ser escrito à mão."""
        codigo = (self.env['res.partner'].browse(partner_id).primavera_customer_code or '').strip() if partner_id else ''
        if not codigo_artigo or not codigo:
            return {'lotes': [], 'mensagem': _("Cliente sem código Primavera — escreva o lote.")}
        with self.env['formularios.primavera.leitura']._ligacao() as ler:
            linhas = ler.q("""
                SELECT TOP 50 l.Lote, MAX(c.Data), SUM(l.Quantidade),
                       MAX(c.TipoDoc + ' ' + c.Serie + '/' + CAST(c.NumDoc AS varchar(12)))
                FROM LinhasDoc l
                JOIN CabecDoc c ON c.Id = l.IdCabecDoc
                LEFT JOIN CabecDocStatus s ON s.IdCabecDoc = c.Id
                WHERE c.TipoDoc IN ('FA', 'FAT', 'FRT') AND ISNULL(s.Anulado, 0) = 0
                  AND c.Entidade = %s AND l.Artigo = %s AND l.Quantidade > 0
                  AND ISNULL(l.Lote, '') <> '' AND LEFT(l.Lote, 1) <> '<'
                GROUP BY l.Lote
                ORDER BY MAX(c.Data) DESC""", codigo, codigo_artigo.strip())
        lotes = [{'lote': lote, 'data': data.strftime('%d/%m/%Y'), 'quantidade': qtd, 'documento': doc}
                 for lote, data, qtd, doc in linhas]
        return {'lotes': lotes,
                'mensagem': '' if lotes else _("Sem lotes deste artigo faturados a este cliente — escreva o lote.")}

    @api.onchange('artigo_id')
    def _onchange_artigo_id(self):
        for rec in self:
            if rec.artigo_id:
                rec.codigo_artigo = rec.artigo_id.primavera_code or rec.artigo_id.default_code or False
                rec.descricao_artigo = rec.artigo_id.name or False
