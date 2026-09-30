import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

INSTALL_DATE_PARAM = "mirazeite_partner_nif_dedup.install_date"

WATCHED_MERGE_VATS = {
    "B10325280": {
        "label": "ZORZALIA SL",
        "email_to": "goncalo.simoes@mirazeite.com",
        "sent_param": "mirazeite_partner_nif_dedup.zorzalia_alert_sent",
    },
}


def _normalize_vat(v):
    """Retira separadores comuns (espaço, traço, ponto) e uniformiza case."""
    if not v:
        return ""
    return v.replace(" ", "").replace("-", "").replace(".", "").upper()


class ResPartner(models.Model):
    _inherit = "res.partner"

    # ────────────────────────────────────────────────────────────────
    # Merge automático quando Primavera empurra um NIF já existente
    # ────────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        results = [None] * len(vals_list)
        pending_vals = []
        pending_indices = []

        for i, vals in enumerate(vals_list):
            raw_vat = (vals.get("vat") or "").strip() or False
            vat_norm = _normalize_vat(raw_vat) if raw_vat else ""
            prim_code = vals.get("primavera_customer_code") or vals.get(
                "primavera_supplier_code"
            )
            matched = self.env["res.partner"]
            if vat_norm and prim_code:
                base = self.sudo().with_context(active_test=False)
                # 1ª tentativa: match exacto
                matched = base.search(
                    [
                        ("vat", "=", raw_vat),
                        ("primavera_customer_code", "=", False),
                        ("primavera_supplier_code", "=", False),
                    ],
                    limit=1,
                )
                if not matched:
                    # 2ª tentativa: match normalizado (retira -, espaços, pontos)
                    candidates = base.search(
                        [
                            ("vat", "!=", False),
                            ("primavera_customer_code", "=", False),
                            ("primavera_supplier_code", "=", False),
                        ]
                    )
                    matched = candidates.filtered(
                        lambda p: _normalize_vat(p.vat) == vat_norm
                    )[:1]
            if matched:
                _logger.info(
                    "[nif_dedup] Merge Primavera: partner id=%s (%r) promovido "
                    "com código Primavera %s (vat=%r)",
                    matched.id,
                    matched.name,
                    prim_code,
                    matched.vat,
                )
                matched.sudo().write(vals)
                self._maybe_alert_watched_merge(matched, vat_norm, prim_code)
                results[i] = matched
            else:
                pending_indices.append(i)
                pending_vals.append(vals)

        if pending_vals:
            created = super().create(pending_vals)
            for idx, rec in zip(pending_indices, created):
                results[idx] = rec

        return self.browse([r.id for r in results])

    def _maybe_alert_watched_merge(self, partner, vat_norm, prim_code):
        """Dispara email one-shot quando um NIF em WATCHED_MERGE_VATS
        acabou de ter merge. Usa ir.config_parameter como flag para não
        repetir."""
        watched = WATCHED_MERGE_VATS.get(vat_norm)
        if not watched:
            return
        ICP = self.env["ir.config_parameter"].sudo()
        if ICP.get_param(watched["sent_param"]):
            return  # já enviado antes
        try:
            subject = _(
                "[mirazeite_partner_nif_dedup] MERGE OK — %(label)s"
            ) % {"label": watched["label"]}
            body = _(
                "<p>Confirmação de que o módulo <b>mirazeite_partner_nif_dedup"
                "</b> funcionou correctamente.</p>"
                "<ul>"
                "<li>Partner Odoo: <b>#%(pid)s — %(pname)s</b></li>"
                "<li>NIF: <b>%(vat)s</b></li>"
                "<li>Código Primavera atribuído: <b>%(code)s</b></li>"
                "</ul>"
                "<p>O contacto manual que já existia em Odoo foi promovido "
                "(merge) em vez de ter sido criado um duplicado. Todas as "
                "leads/vendas/facturas ligadas a este contacto mantêm-se "
                "intactas.</p>"
                "<p>Este alerta só é enviado uma vez por NIF.</p>"
            ) % {
                "pid": partner.id,
                "pname": partner.name,
                "vat": partner.vat,
                "code": prim_code,
            }
            self.env["mail.mail"].sudo().create({
                "subject": subject,
                "body_html": body,
                "email_to": watched["email_to"],
                "auto_delete": True,
            }).send()
            ICP.set_param(watched["sent_param"], "1")
            _logger.info(
                "[nif_dedup] Alerta email enviado a %s para NIF %s (partner "
                "id=%s)",
                watched["email_to"],
                vat_norm,
                partner.id,
            )
        except Exception:
            _logger.exception(
                "[nif_dedup] Falha a enviar alerta email para NIF %s",
                vat_norm,
            )

    # ────────────────────────────────────────────────────────────────
    # Constraint: NIF obrigatório em partners criados após install
    # ────────────────────────────────────────────────────────────────
    @api.constrains(
        "vat",
        "is_company",
        "parent_id",
        "primavera_customer_code",
        "primavera_supplier_code",
    )
    def _check_vat_required_post_install(self):
        install_date_str = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(INSTALL_DATE_PARAM)
        )
        if not install_date_str:
            return
        install_date = fields.Datetime.from_string(install_date_str)

        for partner in self:
            if not partner.is_company:
                continue
            if not partner.create_date or partner.create_date < install_date:
                continue
            if (
                partner.primavera_customer_code
                or partner.primavera_supplier_code
            ):
                continue
            if partner.vat:
                continue

            raise ValidationError(
                _(
                    "É obrigatório preencher o NIF no contacto %(name)s.\n\n"
                    "Enquanto não tiveres o NIF, deixa a lead com o nome da "
                    "empresa no campo 'Nome da Empresa' (texto) e cria o "
                    "contacto só quando souberes o NIF. Assim evitamos "
                    "duplicados quando o cliente for sincronizado do "
                    "Primavera."
                )
                % {"name": partner.name or _("(sem nome)")}
            )

    # ────────────────────────────────────────────────────────────────
    # Aviso onchange: email já usado noutra empresa
    # ────────────────────────────────────────────────────────────────
    @api.onchange("email", "is_company")
    def _onchange_email_warn_shared(self):
        if not self.email or not self.is_company:
            return
        email_norm = self.email.strip()
        if not email_norm:
            return
        domain = [
            ("email", "=ilike", email_norm),
            ("is_company", "=", True),
        ]
        current_id = self.id or (self._origin and self._origin.id) or 0
        if current_id:
            domain.append(("id", "!=", current_id))
        others = self.env["res.partner"].search(domain, limit=3)
        if not others:
            return
        names = ", ".join(others.mapped("name"))
        return {
            "warning": {
                "title": _("Email já usado noutra empresa"),
                "message": _(
                    "O email %(email)s já está registado em: %(names)s.\n\n"
                    "Isto pode gerar leads mal-ligadas por email. "
                    "Confirma se é mesmo a mesma entidade antes de guardar."
                )
                % {"email": email_norm, "names": names},
            }
        }
