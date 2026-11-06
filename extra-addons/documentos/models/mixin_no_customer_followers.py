from odoo import models


_ALLOWED_MODELS_FOR_CUSTOMER_FOLLOWERS = {
    'res.partner', 'mail.channel', 'discuss.channel',
    'project.task', 'project.project', 'helpdesk.ticket',
    'website.visitor', 'mailing.trace', 'mailing.mailing', 'mail.mass_mailing',
}


def _internal_partner_ids(env):
    """Devolve os partner_ids que são utilizadores internos da Mirazeite.
    Apenas estes podem ser followers/destinatários sugeridos."""
    users = env['res.users'].sudo().search([
        ('active', '=', True),
        ('share', '=', False),   # exclui portal / público
    ])
    return set(users.mapped('partner_id').ids)


def _filter_customers_from_recipients(env, recipients, model_name):
    """Mantém apenas partners que sejam utilizadores internos.
    Qualquer partner externo (cliente, fornecedor, contacto solto) é removido."""
    if not recipients or model_name in _ALLOWED_MODELS_FOR_CUSTOMER_FOLLOWERS:
        return recipients
    partner_ids = [r.get('partner_id') for r in recipients if r.get('partner_id')]
    if not partner_ids:
        return recipients
    internal = _internal_partner_ids(env)
    return [r for r in recipients if r.get('partner_id') in internal or not r.get('partner_id')]


def _filter_customers_from_partner_ids(env, partner_ids, model_name):
    """Mantém apenas partners que sejam utilizadores internos."""
    if not partner_ids or model_name in _ALLOWED_MODELS_FOR_CUSTOMER_FOLLOWERS:
        return partner_ids
    internal = _internal_partner_ids(env)
    return [pid for pid in partner_ids if pid in internal]


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def message_subscribe(self, partner_ids=None, subtype_ids=None):
        partner_ids = _filter_customers_from_partner_ids(self.env, partner_ids, self._name)
        return super().message_subscribe(partner_ids=partner_ids, subtype_ids=subtype_ids)

    def _message_get_suggested_recipients(self):
        recipients = super()._message_get_suggested_recipients()
        return _filter_customers_from_recipients(self.env, recipients, self._name)


class AccountMove(models.Model):
    _inherit = 'account.move'

    def message_subscribe(self, partner_ids=None, subtype_ids=None):
        partner_ids = _filter_customers_from_partner_ids(self.env, partner_ids, self._name)
        return super().message_subscribe(partner_ids=partner_ids, subtype_ids=subtype_ids)

    def _message_get_suggested_recipients(self):
        recipients = super()._message_get_suggested_recipients()
        return _filter_customers_from_recipients(self.env, recipients, self._name)


class PackingList(models.Model):
    _inherit = 'packing.list'

    def message_subscribe(self, partner_ids=None, subtype_ids=None):
        partner_ids = _filter_customers_from_partner_ids(self.env, partner_ids, self._name)
        return super().message_subscribe(partner_ids=partner_ids, subtype_ids=subtype_ids)

    def _message_get_suggested_recipients(self):
        recipients = super()._message_get_suggested_recipients()
        return _filter_customers_from_recipients(self.env, recipients, self._name)


class CertificadoNarrativoAbstract(models.AbstractModel):
    _inherit = 'certificado.narrativo.abstract'

    def message_subscribe(self, partner_ids=None, subtype_ids=None):
        partner_ids = _filter_customers_from_partner_ids(self.env, partner_ids, self._name)
        return super().message_subscribe(partner_ids=partner_ids, subtype_ids=subtype_ids)

    def _message_get_suggested_recipients(self):
        recipients = super()._message_get_suggested_recipients()
        return _filter_customers_from_recipients(self.env, recipients, self._name)


class CertificadoConformidade(models.Model):
    _inherit = 'certificado.conformidade.alimentar'

    def message_subscribe(self, partner_ids=None, subtype_ids=None):
        partner_ids = _filter_customers_from_partner_ids(self.env, partner_ids, self._name)
        return super().message_subscribe(partner_ids=partner_ids, subtype_ids=subtype_ids)

    def _message_get_suggested_recipients(self):
        recipients = super()._message_get_suggested_recipients()
        return _filter_customers_from_recipients(self.env, recipients, self._name)


class BoletimAnalises(models.Model):
    _inherit = 'boletim.analises'

    def message_subscribe(self, partner_ids=None, subtype_ids=None):
        partner_ids = _filter_customers_from_partner_ids(self.env, partner_ids, self._name)
        return super().message_subscribe(partner_ids=partner_ids, subtype_ids=subtype_ids)

    def _message_get_suggested_recipients(self):
        recipients = super()._message_get_suggested_recipients()
        return _filter_customers_from_recipients(self.env, recipients, self._name)


class DeclaracaoLote(models.Model):
    _inherit = 'declaracao.lote'

    def message_subscribe(self, partner_ids=None, subtype_ids=None):
        partner_ids = _filter_customers_from_partner_ids(self.env, partner_ids, self._name)
        return super().message_subscribe(partner_ids=partner_ids, subtype_ids=subtype_ids)

    def _message_get_suggested_recipients(self):
        recipients = super()._message_get_suggested_recipients()
        return _filter_customers_from_recipients(self.env, recipients, self._name)


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    def message_subscribe(self, partner_ids=None, subtype_ids=None):
        partner_ids = _filter_customers_from_partner_ids(self.env, partner_ids, self._name)
        return super().message_subscribe(partner_ids=partner_ids, subtype_ids=subtype_ids)

    def _message_get_suggested_recipients(self):
        recipients = super()._message_get_suggested_recipients()
        return _filter_customers_from_recipients(self.env, recipients, self._name)
