from odoo import api, models

# Domínios que são sempre publicidade da plataforma Wix
_SPAM_DOMAINS = (
    'notifications.wix.com',   # wix-team@notifications.wix.com
)

# Palavras no assunto que indicam notificação Wix (não contacto de cliente)
# Aplica-se apenas a emails do domínio wixsiteautomations.com
_SPAM_SUBJECTS = (
    'otimização',
    'otimizações',
    'campanha',
    'plano de conteúdo',
    'google ads',
    'novo rascunho',
    'está pronto',
    'estão prontos',
    'estão prontas',
)


def _is_spam(email_from, name=''):
    if not email_from:
        return False
    ef = email_from.lower()
    # 1. Domínios de notificação Wix — sempre bloquear
    if any(domain in ef for domain in _SPAM_DOMAINS):
        return True
    # 2. wixsiteautomations.com — bloquear só se assunto tiver keywords Wix
    if 'wixsiteautomations.com' in ef:
        name_lower = (name or '').lower()
        return any(kw in name_lower for kw in _SPAM_SUBJECTS)
    return False


class CrmLeadSpamFilter(models.Model):
    _inherit = 'crm.lead'

    @api.model_create_multi
    def create(self, vals_list):
        clean = [
            v for v in vals_list
            if not _is_spam(v.get('email_from', ''), v.get('name', ''))
        ]
        if not clean:
            return self.browse()
        return super().create(clean)
