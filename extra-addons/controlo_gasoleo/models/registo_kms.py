from datetime import timedelta
from html import escape

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


RELATORIO_MENSAL_EMAILS = [
    'ricardo.nunes@mirazeite.com',
    'goncalo.simoes@mirazeite.com',
    'filomena.furtado@mirazeite.com',
]


class RegistoKms(models.Model):
    _name = 'gasoleo.registo.kms'
    _description = 'Registo de Quilómetros e Abastecimentos'

    veiculo_id = fields.Many2one('gasoleo.veiculo', string='Veículo', required=True)
    condutor_id = fields.Many2one('gasoleo.condutor', string='Condutor', required=True)
    deposito_id = fields.Many2one('gasoleo.deposito', string='Depósito', required=True)

    kms = fields.Float(string='Quilómetros', required=True)
    litros = fields.Float(string='Litros Abastecidos', required=True)
    data = fields.Date(string='Data', default=fields.Date.today)

    @api.constrains('litros')
    def _check_litros_positive(self):
        for rec in self:
            if rec.litros <= 0:
                raise ValidationError(_('Os litros têm de ser maior que zero.'))

    def _deposito_subtrair(self, deposito, litros):
        if not deposito or litros <= 0:
            return
        dep = deposito.sudo()
        if dep.litros < litros:
            raise ValidationError(_(
                'Não há litros suficientes no depósito "%s". Disponível: %s | Pedido: %s'
            ) % (dep.localizacao, dep.litros, litros))
        dep.litros -= litros

    def _deposito_adicionar(self, deposito, litros):
        if not deposito or litros <= 0:
            return
        deposito.sudo().litros += litros

    @api.model_create_multi
    def create(self, vals_list):
        depositos_cache = {}
        for vals in vals_list:
            deposito_id = vals.get('deposito_id')
            litros = float(vals.get('litros') or 0.0)
            if deposito_id:
                deposito = depositos_cache.get(deposito_id) or self.env['gasoleo.deposito'].browse(deposito_id)
                depositos_cache[deposito_id] = deposito
                self._deposito_subtrair(deposito, litros)
        return super().create(vals_list)

    def write(self, vals):
        for rec in self:
            old_deposito = rec.deposito_id
            old_litros = rec.litros or 0.0

            new_deposito = old_deposito
            if 'deposito_id' in vals:
                new_deposito = self.env['gasoleo.deposito'].browse(vals.get('deposito_id'))

            new_litros = float(vals.get('litros', old_litros) or 0.0)

            if (new_deposito != old_deposito) or (new_litros != old_litros):
                self._deposito_adicionar(old_deposito, old_litros)
                try:
                    self._deposito_subtrair(new_deposito, new_litros)
                except Exception:
                    self._deposito_subtrair(old_deposito, old_litros)
                    raise
        return super().write(vals)

    def unlink(self):
        for rec in self:
            rec._deposito_adicionar(rec.deposito_id, rec.litros or 0.0)
        return super().unlink()

    @api.model
    def _get_periodo_relatorio_mensal(self, data_referencia=None):
        data_referencia = data_referencia or fields.Date.context_today(self)
        if isinstance(data_referencia, str):
            data_referencia = fields.Date.from_string(data_referencia)
        inicio = data_referencia.replace(day=1)
        fim = data_referencia + timedelta(days=1)
        return inicio, fim

    @api.model
    def _format_litros(self, litros):
        return f'{litros or 0.0:,.2f}'.replace(',', ' ').replace('.', ',')

    @api.model
    def _read_group_litros(self, domain, groupby_field):
        rows = self.sudo().read_group(
            domain,
            ['litros:sum'],
            [groupby_field],
            orderby=f'{groupby_field} asc',
            lazy=False,
        )
        result = []
        for row in rows:
            group_value = row.get(groupby_field)
            nome = group_value[1] if group_value else 'Sem valor'
            result.append({
                'nome': nome,
                'litros': row.get('litros') or 0.0,
            })
        return result

    @api.model
    def _render_tabela_relatorio_mensal(self, titulo, rows):
        if not rows:
            return f'''
                <h3>{escape(titulo)}</h3>
                <p>Sem registos no período.</p>
            '''

        linhas = ''.join(
            f'''
                <tr>
                    <td style="padding:6px 8px;border-bottom:1px solid #ddd;">{escape(row['nome'])}</td>
                    <td style="padding:6px 8px;border-bottom:1px solid #ddd;text-align:right;">{self._format_litros(row['litros'])}</td>
                </tr>
            '''
            for row in rows
        )
        return f'''
            <h3>{escape(titulo)}</h3>
            <table style="border-collapse:collapse;width:100%;max-width:720px;">
                <thead>
                    <tr>
                        <th style="padding:6px 8px;border-bottom:2px solid #999;text-align:left;">Nome</th>
                        <th style="padding:6px 8px;border-bottom:2px solid #999;text-align:right;">Litros</th>
                    </tr>
                </thead>
                <tbody>{linhas}</tbody>
            </table>
        '''

    @api.model
    def _get_body_relatorio_mensal(self, inicio, fim):
        domain = [
            ('data', '>=', inicio),
            ('data', '<', fim),
        ]
        total_litros = sum(self.sudo().search(domain).mapped('litros'))
        periodo = f'{inicio.strftime("%d/%m/%Y")} a {(fim - timedelta(days=1)).strftime("%d/%m/%Y")}'

        tabelas = [
            self._render_tabela_relatorio_mensal(
                'Total de litros por Condutor',
                self._read_group_litros(domain, 'condutor_id'),
            ),
            self._render_tabela_relatorio_mensal(
                'Total de litros por Veículo',
                self._read_group_litros(domain, 'veiculo_id'),
            ),
            self._render_tabela_relatorio_mensal(
                'Total de litros por Depósito',
                self._read_group_litros(domain, 'deposito_id'),
            ),
        ]

        return f'''
            <p>Segue o relatório mensal de gasóleo referente ao período <strong>{escape(periodo)}</strong>.</p>
            <p><strong>Total mensal:</strong> {self._format_litros(total_litros)} litros</p>
            {''.join(tabelas)}
        '''

    @api.model
    def _cron_enviar_relatorio_mensal_gasoleo(self):
        inicio, fim = self._get_periodo_relatorio_mensal()
        body = self._get_body_relatorio_mensal(inicio, fim)
        periodo = f'{inicio.strftime("%d/%m/%Y")} a {(fim - timedelta(days=1)).strftime("%d/%m/%Y")}'

        mail = self.env['mail.mail'].sudo().create({
            'subject': f'Relatório Mensal de Gasóleo - {periodo}',
            'email_from': 'noreply@mirazeite.com',
            'email_to': ','.join(RELATORIO_MENSAL_EMAILS),
            'body_html': body,
        })
        mail.sudo().send()
        return True
