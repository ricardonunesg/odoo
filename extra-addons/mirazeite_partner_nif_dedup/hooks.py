import logging

from odoo import fields

_logger = logging.getLogger(__name__)

INSTALL_DATE_PARAM = "mirazeite_partner_nif_dedup.install_date"
MIRAZEITE_OWN_PARTNER_ID = 1725
SHARED_EMAIL_MARKER = "geral@mirazeite.com"


def post_init(env):
    """Executado uma vez na instalação:
    1) Fixa install_date (data de corte para o gate NIF).
    2) Limpa emails partilhados dos partners contaminados.
    3) Desliga partner_id das leads mal-ligadas por email partilhado.
    """
    _stamp_install_date(env)
    _cleanup_shared_emails(env)


def _stamp_install_date(env):
    now = fields.Datetime.now()
    env["ir.config_parameter"].sudo().set_param(
        INSTALL_DATE_PARAM,
        fields.Datetime.to_string(now),
    )
    _logger.info(
        "[nif_dedup] install_date fixado em %s — partners criados a partir "
        "de agora obrigam NIF (empresas)",
        now,
    )


def _cleanup_shared_emails(env):
    Partner = env["res.partner"].sudo()
    Lead = env["crm.lead"].sudo()

    contaminated = Partner.search(
        [("email", "ilike", f"%{SHARED_EMAIL_MARKER}%")]
    )
    own = Partner.browse(MIRAZEITE_OWN_PARTNER_ID).exists()
    if own and own.name and "MIRAZEITE" in own.name.upper():
        to_clean = contaminated - own
        _logger.info(
            "[nif_dedup] Preservado email em partner id=%s (%r)",
            own.id,
            own.name,
        )
    else:
        to_clean = contaminated
        _logger.warning(
            "[nif_dedup] Partner id=%s não encontrado ou não é MIRAZEITE — "
            "vou limpar email de todos os %d contaminados",
            MIRAZEITE_OWN_PARTNER_ID,
            len(contaminated),
        )

    if not to_clean:
        _logger.info(
            "[nif_dedup] Nenhum partner com %s encontrado — saneamento skip",
            SHARED_EMAIL_MARKER,
        )
        return

    bad_leads = Lead.search([("partner_id", "in", to_clean.ids)])
    _logger.info(
        "[nif_dedup] A desligar partner_id de %d leads mal-ligadas "
        "(partners contaminados: %d)",
        len(bad_leads),
        len(to_clean),
    )
    if bad_leads:
        bad_leads.write({"partner_id": False})

    _logger.info(
        "[nif_dedup] A limpar campo email em %d partners contaminados",
        len(to_clean),
    )
    to_clean.write({"email": False})

    _logger.info(
        "[nif_dedup] Saneamento concluído: %d partners limpos, %d leads "
        "desligadas",
        len(to_clean),
        len(bad_leads),
    )
