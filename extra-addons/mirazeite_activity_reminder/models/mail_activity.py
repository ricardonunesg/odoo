import logging
from datetime import datetime, time

import pytz
from markupsafe import Markup

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

TZ = pytz.timezone('Europe/Lisbon')
REMINDER_HOUR = 8
BATCH = 200


class MailActivity(models.Model):
    _inherit = 'mail.activity'

    mirazeite_reminder_date = fields.Date(
        'Lembrete do prazo enviado em', copy=False, readonly=True,
        help='Dia em que foi enviado o lembrete "prazo hoje" (evita lembretes repetidos).')

    @api.model
    def _mirazeite_cron_due_today_reminders(self, now=None):
        """Lembrete de cada atividade com prazo para hoje.

        Corre de hora a hora; só trabalha a partir das 08:00 de Lisboa. Abrange as
        atividades que já existiam às 08:00 (as criadas depois já tiveram o aviso de
        atribuição) e ainda não tiveram lembrete hoje."""
        now_utc = now or fields.Datetime.now()
        now_local = pytz.utc.localize(now_utc).astimezone(TZ)
        if now_local.hour < REMINDER_HOUR:
            return
        today = now_local.date()
        cutoff = TZ.localize(datetime.combine(today, time(REMINDER_HOUR))) \
            .astimezone(pytz.utc).replace(tzinfo=None)

        activities = self.sudo().search([
            ('date_deadline', '=', today),
            ('user_id', '!=', False),
            ('user_id.active', '=', True),
            ('user_id.share', '=', False),
            ('create_date', '<', cutoff),
            '|', ('mirazeite_reminder_date', '=', False),
                 ('mirazeite_reminder_date', '!=', today),
        ], order='id', limit=BATCH + 1)
        if len(activities) > BATCH:
            activities = activities[:BATCH]
            self.env.ref('mirazeite_activity_reminder.ir_cron_activity_due_today').sudo()._trigger()

        sent = 0
        for activity in activities:
            try:
                with self.env.cr.savepoint():
                    activity.mirazeite_reminder_date = today
                    if activity._mirazeite_notify_due_today():
                        sent += 1
            except Exception:
                _logger.exception('Lembrete de atividade: falhou a atividade %s', activity.id)
                # marca na mesma: um erro não deve repetir-se de hora a hora
                activity.mirazeite_reminder_date = today
        if activities:
            _logger.info('Lembrete de atividades (prazo %s): %s enviados de %s', today, sent, len(activities))

    def _mirazeite_notify_due_today(self):
        """Avisa o responsável no registo da atividade, como o aviso de atribuição do
        Odoo: vai pelo canal de cada utilizador (Caixa de entrada ou email) e o nome
        do registo fica clicável."""
        self.ensure_one()
        if not self.res_model or not self.res_id or self.res_model not in self.env:
            return False
        activity = self.with_context(lang=self.user_id.lang) if self.user_id.lang else self
        env = activity.env
        record = env[self.res_model].browse(self.res_id).exists()
        if not record or not hasattr(record, 'message_notify'):
            return False

        model_description = env['ir.model']._get(self.res_model).display_name
        type_name = activity.activity_type_id.name or env._('Activity')
        lines = [Markup('<li>%s %s</li>') % (env._('Activity:'), type_name)]
        if activity.summary:
            lines.append(Markup('<li>%s %s</li>') % (env._('Summary:'), activity.summary))
        lines.append(Markup('<li>%s %s (%s)</li>') % (env._('Document:'), self.res_name or '', model_description))
        body = Markup('<p>%s</p><ul>%s</ul>') % (env._('This activity is due today:'), Markup('').join(lines))

        record.message_notify(
            partner_ids=self.user_id.partner_id.ids,
            body=body,
            record_name=self.res_name,
            model_description=model_description,
            email_layout_xmlid='mail.mail_notification_layout',
            subject=env._('"%(activity_name)s: %(summary)s" is due today',
                          activity_name=self.res_name,
                          summary=activity.summary or type_name),
            subtitles=[env._('Activity: %s', type_name), env._('Deadline: today')],
        )
        return True
