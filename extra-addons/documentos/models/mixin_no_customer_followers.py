from odoo import _, api, models
from odoo.exceptions import UserError


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


def _crm_block_external_recipients(env, partner_ids):
    """Oportunidades: recusa com aviso qualquer destinatário que não seja
    utilizador interno activo (o OdooBot é a única excepção). Nada é enviado."""
    external_ids = {pid for pid in partner_ids or [] if isinstance(pid, int)}
    external_ids -= _internal_partner_ids(env)
    external_ids.discard(env.ref('base.partner_root').id)
    if external_ids:
        names = env['res.partner'].sudo().browse(sorted(external_ids)).mapped('display_name')
        raise UserError(_(
            "As mensagens das oportunidades são só internas e nada foi enviado.\n"
            "Retire estes destinatários externos: %(names)s",
            names=", ".join(name or "?" for name in names),
        ))


class CrmLead(models.Model):
    """Nas oportunidades as mensagens são só internas.

    Os emails recebidos entram como OdooBot (inactivo): nunca são recusados aqui
    e os seus autores continuam a aparecer no histórico, mas sem ficarem seguidores.
    """
    _inherit = 'crm.lead'

    def _message_subscribe(self, partner_ids=None, subtype_ids=None, customer_ids=None):
        # É aqui, e não em message_subscribe, que passa o autor de um email recebido.
        partner_ids = _filter_customers_from_partner_ids(self.env, partner_ids, self._name)
        return super()._message_subscribe(
            partner_ids=partner_ids, subtype_ids=subtype_ids, customer_ids=customer_ids,
        )

    def _message_get_suggested_recipients(self):
        recipients = super()._message_get_suggested_recipients()
        internal = _internal_partner_ids(self.env)
        return [r for r in recipients if r.get('partner_id') in internal]

    def _notify_get_recipients(self, message, msg_vals, **kwargs):
        # Última barreira: seguidores antigos ou destinatários de sistema nunca recebem.
        recipients = super()._notify_get_recipients(message, msg_vals, **kwargs)
        internal = _internal_partner_ids(self.env)
        return [r for r in recipients if r['id'] in internal]

    @api.returns('mail.message', lambda value: value.id)
    def message_post(self, **kwargs):
        message_type = kwargs.get('message_type')
        user = self.env.user
        # Só mensagens escritas por pessoas: o gateway e os crons correm como OdooBot.
        if user.active and not user.share:
            if message_type == 'sms':
                raise UserError(_("Não é permitido enviar SMS a partir das oportunidades."))
            if message_type in ('comment', 'email_outgoing'):
                _crm_block_external_recipients(self.env, kwargs.get('partner_ids'))
        return super().message_post(**kwargs)

    def _sms_get_recipients_info(self, force_field=False, partner_fallback=True):
        # Todos os SMS passam por aqui; assim não é preciso depender do módulo sms.
        raise UserError(_("Não é permitido enviar SMS a partir das oportunidades."))


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    def _crm_check_internal_only(self):
        for wizard in self.filtered(lambda w: w.model == 'crm.lead'):
            if wizard.composition_mode == 'mass_mail':
                raise UserError(_(
                    "Não é permitido enviar emails em massa a partir das oportunidades."
                ))
            _crm_block_external_recipients(self.env, wizard.partner_ids.ids)

    def action_schedule_message(self, scheduled_date=False):
        self._crm_check_internal_only()
        return super().action_schedule_message(scheduled_date=scheduled_date)

    def _action_send_mail(self, auto_commit=False):
        self._crm_check_internal_only()
        return super()._action_send_mail(auto_commit=auto_commit)


class MailWizardInvite(models.TransientModel):
    _inherit = 'mail.wizard.invite'

    def add_followers(self):
        for wizard in self.filtered(lambda w: w.res_model == 'crm.lead'):
            _crm_block_external_recipients(self.env, wizard.partner_ids.ids)
        return super().add_followers()
