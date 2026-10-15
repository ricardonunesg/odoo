import logging
import re
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytz

from odoo import SUPERUSER_ID, api, fields, models
from odoo.http import _request_stack
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)

POSTCOMMIT_KEY = 'mirazeite.push.queue'
MAX_BODY = 240
TZ = pytz.timezone('Europe/Lisbon')
LAST_SUMMARY_KEY = 'mirazeite.push.last_summary'
ASSIGNED_RE = re.compile(r'^(You have been assigned to|Você foi atribuído a|Foi atribuído a)\s+', re.I)


def _clean_text(html):
    text = html2plaintext(html or '')
    # html2plaintext põe os links como "texto [1]" + lista "[1] url" no fim
    text = re.sub(r'^\s*\[\d+\]\s+\S+\s*$', '', text, flags=re.M)
    text = re.sub(r'\s*\[\d+\]', '', text)
    text = re.sub(r'\*(\S[^*]*?)\*', r'\1', text)  # negrito "*texto*"
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > MAX_BODY:
        text = text[:MAX_BODY - 1].rstrip() + '…'
    return text


class KitsMobilePushNotification(models.Model):
    _inherit = 'kits.mobile.push.notification'

    def send_push_notification_with_link(self, notify_user_ids, notification_title, notification_body,
                                         click_action=False, image_url=False):
        """Em vez de enviar logo (dentro da transacção, com erros escondidos),
        põe o push numa fila que só é enviada depois do commit."""
        if self.env.context.get('mirazeite_push_skip') or not notify_user_ids:
            return
        if not self.env.context.get('mirazeite_push_force') and self._mirazeite_is_quiet():
            # horário de silêncio: fica só na Caixa de entrada; resumo de manhã
            return
        tokens = self.sudo().search([
            ('user_id', 'in', list(notify_user_ids)),
            ('user_login', '=', True),
            ('firebase_token', '!=', False),
        ]).mapped('firebase_token')
        if not tokens or not notification_title or not notification_body:
            return
        cr = self.env.cr
        queue = cr.postcommit.data.setdefault(POSTCOMMIT_KEY, [])
        if not queue:
            cr.postcommit.add(lambda: self._mirazeite_flush_push(cr.dbname, queue))
        queue.append({
            'tokens': list(dict.fromkeys(tokens)),
            'title': notification_title,
            'body': notification_body,
            'click_action': click_action,
            'image_url': image_url,
        })

    def _mirazeite_flush_push(self, dbname, queue):
        """Envia os pushes em fila, já depois do commit, com um cursor novo.

        O código de envio da Keypress usa `request.env`; para funcionar também
        a partir de crons (sem pedido web), põe-se temporariamente um `request`
        mínimo só com `env`."""
        from odoo.modules.registry import Registry
        try:
            with Registry(dbname).cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                _request_stack.push(SimpleNamespace(env=env))
                try:
                    method = env['connect.server'].get_method(
                        'push_notification', 'send_push_notification_with_link', {})
                    code = method.get('method') if isinstance(method, dict) else False
                    if not code:
                        _logger.warning('Push: servidor Keypress não devolveu o código de envio (%s)',
                                        method.get('error') if isinstance(method, dict) else method)
                        return
                    for item in queue:
                        localdict = {
                            'hardware_ids': [{'firebase_token': t} for t in item['tokens']],
                            'notification_title': item['title'],
                            'notification_body': item['body'],
                            'click_action': item['click_action'],
                            'image_url': item['image_url'],
                        }
                        try:
                            exec(code, localdict)
                        except Exception:
                            _logger.exception('Push: falhou o envio de "%s"', item['title'])
                finally:
                    _request_stack.pop()
        except Exception:
            _logger.exception('Push: erro ao preparar o envio')

    @api.model
    def _mirazeite_push_inbox(self, notifications):
        """Um push por cada notificação nova na Caixa de entrada do Discuss."""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        by_message = {}
        for notif in notifications:
            by_message.setdefault(notif.mail_message_id, self.env['res.partner'])
            by_message[notif.mail_message_id] |= notif.res_partner_id
        for message, partners in by_message.items():
            users = partners.user_ids.filtered(lambda u: u.active and not u.share)
            if not users:
                continue
            title, body = self._mirazeite_inbox_texts(message)
            if not body:
                continue
            click_action = False
            if message.model and message.res_id:
                click_action = f"{base_url}/web#model={message.model}&id={message.res_id}&view_type=form"
            self.send_push_notification_with_link(
                notify_user_ids=users.ids,
                notification_title=title,
                notification_body=body,
                click_action=click_action,
            )

    @api.model
    def _mirazeite_inbox_texts(self, message):
        title = message.record_name
        if not title and message.model and message.res_id:
            record = self.env[message.model].sudo().browse(message.res_id).exists()
            title = record.display_name if record else False
        title = title or message.subject or 'Odoo'

        if message.message_type == 'user_notification' and message.subject:
            # atribuições ("You have been assigned to …"), atividades, etc.
            subject = message.subject
            if ASSIGNED_RE.match(subject):
                subject = 'Foi-lhe atribuída: ' + ASSIGNED_RE.sub('', subject)
            return title, _clean_text(subject)

        text = _clean_text(message.body)
        if not text and message.tracking_value_ids:
            changes = message.sudo().tracking_value_ids._tracking_value_format()
            text = '; '.join(
                f"{c['changedField']}: {c['oldValue']['value'] or '—'} → {c['newValue']['value'] or '—'}"
                for c in changes
            )
            text = _clean_text(text)
        if not text:
            text = _clean_text(message.subject or '')
        if text and message.author_id and message.message_type in ('comment', 'email'):
            text = _clean_text(f"{message.author_id.name}: {text}")
        return title, text

    # ------------------------------------------------------------------
    # Horário de silêncio (por defeito 21h–8h nos dias úteis e todo o fim
    # de semana, hora de Lisboa) e resumo da manhã.
    # ------------------------------------------------------------------

    @api.model
    def _mirazeite_quiet_config(self):
        ICP = self.env['ir.config_parameter'].sudo()
        return (
            int(ICP.get_param('mirazeite.push.quiet_start', 21)),
            int(ICP.get_param('mirazeite.push.quiet_end', 8)),
            ICP.get_param('mirazeite.push.quiet_weekend', 'True') == 'True',
        )

    @api.model
    def _mirazeite_is_quiet(self, local_dt=None, config=None):
        start, end, weekend = config or self._mirazeite_quiet_config()
        local_dt = local_dt or datetime.now(pytz.utc).astimezone(TZ)
        if weekend and local_dt.weekday() >= 5:
            return True
        return local_dt.hour >= start or local_dt.hour < end

    @api.model
    def _mirazeite_last_quiet_window(self, now_local):
        """Devolve (início, fim) do último período de silêncio já terminado."""
        config = self._mirazeite_quiet_config()
        hour = timedelta(hours=1)
        end = now_local.replace(minute=0, second=0, microsecond=0)
        for _i in range(24 * 7):
            if self._mirazeite_is_quiet(end - hour, config):
                break
            end -= hour
        start = end
        for _i in range(24 * 7):
            if not self._mirazeite_is_quiet(start - hour, config):
                break
            start -= hour
        return start, end

    @api.model
    def _mirazeite_cron_quiet_summary(self):
        """Corre de hora a hora. Na primeira hora fora do silêncio, envia a cada
        pessoa um único push com o número de avisos por ler que chegaram à
        Caixa de entrada durante o silêncio."""
        if self._mirazeite_is_quiet():
            return
        ICP = self.env['ir.config_parameter'].sudo()
        now_local = datetime.now(pytz.utc).astimezone(TZ)
        start_local, end_local = self._mirazeite_last_quiet_window(now_local)
        start_utc = start_local.astimezone(pytz.utc).replace(tzinfo=None)
        end_utc = end_local.astimezone(pytz.utc).replace(tzinfo=None)
        last = ICP.get_param(LAST_SUMMARY_KEY)
        if last and fields.Datetime.from_string(last) >= end_utc:
            return  # já enviado para este período
        ICP.set_param(LAST_SUMMARY_KEY, fields.Datetime.to_string(end_utc))

        self.env.cr.execute("""
            SELECT n.res_partner_id, count(*)
              FROM mail_notification n
              JOIN mail_message m ON m.id = n.mail_message_id
             WHERE n.notification_type = 'inbox'
               AND NOT n.is_read
               AND m.create_date >= %s AND m.create_date < %s
             GROUP BY n.res_partner_id
        """, (start_utc, end_utc))
        counts = dict(self.env.cr.fetchall())
        if not counts:
            return
        base_url = ICP.get_param('web.base.url', '')
        weekend = start_local.weekday() == 4 and (end_local - start_local) > timedelta(hours=24)
        title = 'Avisos do fim de semana' if weekend else 'Avisos da noite'
        Push = self.with_context(mirazeite_push_force=True)
        for partner in self.env['res.partner'].browse(list(counts)):
            users = partner.user_ids.filtered(lambda u: u.active and not u.share)
            if not users:
                continue
            n = counts[partner.id]
            body = f'Tem {n} aviso novo na Caixa de entrada' if n == 1 else \
                f'Tem {n} avisos novos na Caixa de entrada'
            Push.send_push_notification_with_link(
                notify_user_ids=users.ids,
                notification_title=title,
                notification_body=body,
                click_action=f'{base_url}/odoo/discuss',
            )
