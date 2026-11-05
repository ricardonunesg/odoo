from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """As reclamações deixam de usar Activities: apaga o tipo "Tratar reclamação" (criado na 18.0.1.10.0), que só existe
    para elas. As Activities dos outros tipos e módulos não são tocadas."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    tipo = env.ref('qualidade_reclamacoes.mail_activity_type_tratar_reclamacao', raise_if_not_found=False)
    if tipo:
        env['mail.activity'].with_context(active_test=False).search([('activity_type_id', '=', tipo.id)]).unlink()
        tipo.unlink()
