from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Preenche as 3 linhas de configuração com os valores por defeito (Ricardo responsável, Rita informada),
    só se ainda estiverem vazias. Os 3 tipos continuam DESATIVADOS."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    users = env['res.users'].with_context(active_test=False)
    ricardo = users.search([('login', '=', 'ricardo.machado@mirazeite.com')], limit=1)
    rita = users.search([('login', '=', 'rita.faroleira@mirazeite.com')], limit=1)
    for cfg in env['qualidade.notificacao.config'].search([('responsavel_id', '=', False)]):
        cfg.write({'responsavel_id': ricardo.id, 'informado_ids': [(6, 0, rita.ids)], 'ativo': False})
