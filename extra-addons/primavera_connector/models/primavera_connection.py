import calendar
import html
import re
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

import requests
from dateutil.relativedelta import relativedelta
from markupsafe import Markup
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, html2plaintext

SYNC_FAILURE_ALERT_EMAIL = "goncalo.simoes@mirazeite.com"


class PrimaveraConnection(models.Model):
    _name = "primavera.connection"
    _description = "Ligacao Primavera WebAPI"
    _rec_name = "name"

    # --- Identificação ---
    name = fields.Char(default="Primavera WebAPI", required=True)
    active = fields.Boolean(default=True)

    # --- WebAPI ---
    api_url = fields.Char(
        "URL Base",
        required=True,
        default="http://10.0.10.11:2018/WebApi",
        help="Ex: http://10.0.10.11:2018/WebApi",
    )
    api_username = fields.Char("Utilizador", required=True)
    api_password = fields.Char("Password", required=True, copy=False)
    api_company = fields.Char("Empresa", required=True, default="MIRAZEITE")
    api_instance = fields.Char("Instância", default="Default")
    api_line = fields.Char("Linha", default="evolution")
    api_filial = fields.Char("Filial", default="000")

    # --- O que sincronizar ---
    sync_customers = fields.Boolean("Sincronizar clientes", default=True)
    sync_suppliers = fields.Boolean("Sincronizar fornecedores", default=True)
    sync_products = fields.Boolean("Sincronizar artigos", default=True)
    sync_ecls = fields.Boolean("Sincronizar ECLs (encomendas)", default=True)
    sync_faturas = fields.Boolean("Sincronizar faturas (FA)", default=True)
    sync_employees = fields.Boolean("Sincronizar funcionários", default=True)

    # --- Configuração de pesquisa de funcionários ---
    employee_code_digits = fields.Integer("Dígitos código funcionário", default=3)
    employee_code_max = fields.Integer("Nº máx. funcionários a pesquisar", default=200)
    employee_miss_stop = fields.Integer(
        "Paragens consecutivas para parar (funcionários)",
        default=30,
        help="Para a pesquisa de funcionários após N códigos consecutivos inexistentes.",
    )

    # --- Configuração de pesquisa por código ---
    customer_code_prefix = fields.Char("Prefixo clientes", default="CL")
    customer_code_digits = fields.Integer("Dígitos código cliente", default=4)
    customer_code_max = fields.Integer("Nº máx. clientes a pesquisar", default=999)
    supplier_code_prefix = fields.Char("Prefixo fornecedores", default="FO")
    supplier_code_digits = fields.Integer("Dígitos código fornecedor", default=4)
    supplier_code_max = fields.Integer("Nº máx. fornecedores a pesquisar", default=999)
    consecutive_misses_stop = fields.Integer(
        "Paragens consecutivas para parar",
        default=30,
        help="Para a pesquisa de códigos após N missas consecutivas.",
    )

    # --- Configuração ECL ---
    ecl_serie = fields.Char("Série ECL", default="2026")
    ecl_scan_max = fields.Integer("Nº máx. ECL a pesquisar", default=500)
    ecl_last_imported_num = fields.Integer(
        "Último nº ECL importado", default=0, readonly=True,
        help="Próxima sincronização começa a partir deste número + 1.",
    )
    ecl_miss_stop = fields.Integer(
        "Misses consecutivas para parar (ECL)", default=50,
        help="Para a pesquisa de ECLs após N números consecutivos inexistentes na API.",
    )

    # --- Configuração Faturas (FA) ---
    fa_doc_type = fields.Char("Tipo doc. fatura", default="FA")
    fa_serie = fields.Char("Série FA", default="2026")
    fa_scan_max = fields.Integer("Nº máx. FA a pesquisar", default=500)
    fa_last_imported_num = fields.Integer(
        "Último nº FA importado", default=0, readonly=True,
        help="Próxima sincronização começa a partir deste número + 1.",
    )
    fa_miss_stop = fields.Integer(
        "Misses consecutivas para parar (FA)", default=50,
        help="Para a pesquisa de faturas após N números consecutivos inexistentes na API.",
    )

    # --- Configuração Faturas (FAT) ---
    fat_serie = fields.Char("Série FAT", default="2026")
    fat_scan_max = fields.Integer("Nº máx. FAT a pesquisar", default=500)
    fat_last_imported_num = fields.Integer(
        "Último nº FAT importado", default=0, readonly=True,
        help="Próxima sincronização começa a partir deste número + 1.",
    )
    fat_miss_stop = fields.Integer(
        "Misses consecutivas para parar (FAT)", default=50,
    )
    sync_faturas_fat = fields.Boolean("Sincronizar FAT", default=True)

    # --- SQL Server directo (para validade de lotes) ---
    sql_host = fields.Char("SQL Server Host", default="10.0.10.13")
    sql_port = fields.Integer("SQL Server Port", default=1433)
    sql_database = fields.Char("SQL Server Database", default="MIRAZEITE")
    sql_user = fields.Char("SQL Server Utilizador")
    sql_password = fields.Char("SQL Server Password", copy=False)

    # --- Estado ---
    last_connection_test = fields.Datetime(readonly=True)
    last_connection_message = fields.Text(readonly=True)
    last_sync_date = fields.Datetime(readonly=True)
    last_sync_message = fields.Text(readonly=True)

    # --- Health check / alerta API caída ---
    api_healthy = fields.Boolean("API saudável", default=True, readonly=True)
    api_health_last_check = fields.Datetime("Último health check", readonly=True)
    api_health_fail_since = fields.Datetime("API a falhar desde", readonly=True)
    api_health_last_message = fields.Text("Último erro API", readonly=True)
    alert_email_recipients = fields.Char(
        "Emails para alerta API",
        default="goncalo.simoes@mirazeite.com,ricardo.nunes@mirazeite.com",
        help="Lista separada por vírgulas de emails que recebem aviso quando a API cai/recupera.",
    )

    # ─────────────────────────────────────────────────────────────────────
    # AUTENTICAÇÃO / TOKEN
    # ─────────────────────────────────────────────────────────────────────

    # Cache de tokens por id de registo (por processo/worker; aceitável)
    _token_cache = {}

    def _authenticate(self):
        """Autentica na WebAPI e devolve o access_token."""
        self.ensure_one()
        try:
            r = requests.post(
                f"{self.api_url}/token",
                data={
                    "username": self.api_username,
                    "password": self.api_password,
                    "company": self.api_company,
                    "instance": self.api_instance or "Default",
                    "line": self.api_line or "evolution",
                    "grant_type": "password",
                    "sessionkey": str(uuid.uuid4()),
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=15,
            )
            r.raise_for_status()
        except requests.RequestException as exc:
            raise UserError(_("Erro ao autenticar na Primavera WebAPI: %s") % exc) from exc

        data = r.json()
        token = data["access_token"]
        expires_in = int(data.get("expires_in", 1199))
        PrimaveraConnection._token_cache[self.id] = {
            "token": token,
            "expires_at": datetime.now() + timedelta(seconds=expires_in - 60),
        }
        return token

    def _get_token(self):
        cache = PrimaveraConnection._token_cache.get(self.id, {})
        if cache.get("token") and cache.get("expires_at", datetime.min) > datetime.now():
            return cache["token"]
        return self._authenticate()

    def _headers(self):
        return {"Authorization": f"Bearer {self._get_token()}", "Accept": "application/json"}

    # ─────────────────────────────────────────────────────────────────────
    # HTTP HELPERS
    # ─────────────────────────────────────────────────────────────────────

    def _api_get(self, endpoint, timeout=10):
        """GET endpoint; devolve o dict Results ou None se não existir/erro."""
        self.ensure_one()
        try:
            r = requests.get(f"{self.api_url}{endpoint}", headers=self._headers(), timeout=timeout)
        except requests.Timeout:
            raise UserError(_("Timeout a chamar %s") % endpoint)
        except requests.RequestException as exc:
            raise UserError(_("Erro HTTP em %s: %s") % (endpoint, exc)) from exc

        if r.status_code >= 400:
            return None
        try:
            body = r.json()
        except Exception:
            return None
        if body.get("StatusCode", 200) >= 400 or body.get("ErrorMessage"):
            return None
        return body.get("Results")

    def _exists(self, endpoint):
        results = self._api_get(endpoint)
        return bool(results and results.get("Existe"))

    def _edita(self, endpoint):
        results = self._api_get(endpoint)
        if not results:
            return None
        return results.get("Edita")

    # ─────────────────────────────────────────────────────────────────────
    # ACÇÕES MANUAIS
    # ─────────────────────────────────────────────────────────────────────

    def action_test_connection(self):
        for conn in self:
            try:
                conn._authenticate()
                result = conn._api_get("/v2/Inventario/Armazens/Existe/A1")
                message = _("Ligação OK. Armazém A1 existe: %s") % (
                    result.get("Existe") if result else "?"
                )
                conn.write({
                    "last_connection_test": fields.Datetime.now(),
                    "last_connection_message": message,
                })
                conn._log("connection", "success", message)
            except Exception as exc:
                message = str(exc)
                conn.write({
                    "last_connection_test": fields.Datetime.now(),
                    "last_connection_message": message,
                })
                conn._log("connection", "error", message)
                raise

        return self._notify(_("Primavera"), _("Teste de ligação concluído com sucesso."))

    def action_import_customers(self):
        self.ensure_one()
        stats = self._import_partners("customer")
        return self._notify(_("Clientes importados"), self._stats_msg(stats))

    def action_import_suppliers(self):
        self.ensure_one()
        stats = self._import_partners("supplier")
        return self._notify(_("Fornecedores importados"), self._stats_msg(stats))

    def action_import_products(self):
        self.ensure_one()
        stats = self._sync_products_from_sql(full=True)
        if stats is None:
            raise UserError(_("Sem ligação ao SQL Server do Primavera: os artigos vêm de lá."))
        self._log("products", "success", "[completo] " + self._stats_msg(stats))
        return self._notify(_("Artigos importados"), self._stats_msg(stats))

    def action_import_ecls(self):
        self.ensure_one()
        stats = self._import_ecls()
        return self._notify(_("ECLs importadas"), self._stats_msg(stats))

    def action_import_faturas(self):
        self.ensure_one()
        stats_fa = self._import_faturas_doc("FA", self.fa_serie, self.fa_last_imported_num,
                                             self.fa_scan_max, self.fa_miss_stop, "fa_last_imported_num")
        stats_fat = self._import_faturas_doc("FAT", self.fat_serie, self.fat_last_imported_num,
                                              self.fat_scan_max, self.fat_miss_stop, "fat_last_imported_num")
        msg = _("FA: %s\nFAT: %s") % (self._stats_msg(stats_fa), self._stats_msg(stats_fat))
        return self._notify(_("Faturas importadas"), msg)

    def action_reset_fa_counter(self):
        self.ensure_one()
        self.fa_last_imported_num = 0
        return self._notify(_("FA"), _("Contador reiniciado. Próxima sincronização reimporta todas."))

    def action_reimport_faturas(self):
        """Reinicia contadores e reimporta todas as faturas desde o início.
        Faturas draft são totalmente substituídas.
        Faturas posted recebem actualização dos campos de cabeçalho (importador, ref_cliente, etc.)."""
        self.ensure_one()
        self.write({'fa_last_imported_num': 0, 'fat_last_imported_num': 0})
        stats_fa = self._import_faturas_doc(
            "FA", self.fa_serie, 0,
            self.fa_scan_max, self.fa_miss_stop, "fa_last_imported_num",
        )
        stats_fat = {"created": 0, "updated": 0, "skipped": 0}
        if self.sync_faturas_fat:
            stats_fat = self._import_faturas_doc(
                "FAT", self.fat_serie, 0,
                self.fat_scan_max, self.fat_miss_stop, "fat_last_imported_num",
            )
        total_created = stats_fa["created"] + stats_fat["created"]
        total_updated = stats_fa["updated"] + stats_fat["updated"]
        msg = _("Reimportação concluída.\nCriadas: %s  |  Actualizadas: %s") % (total_created, total_updated)
        self._log("faturas", "success", msg)
        return self._notify(_("Reimportação de Faturas"), msg)

    def action_import_employees(self):
        self.ensure_one()
        stats = self._import_employees()
        return self._notify(_("Funcionários importados"), self._stats_msg(stats))

    def action_repair_ecl_doc_data(self):
        """Sincroniza export_doc_type e ecl_doc_line_ids de todos os ECLs a partir do parceiro."""
        self.ensure_one()
        if "sale.order" not in self.env:
            return self._notify(_("Reparar ECLs"), _("Módulo sale.order não disponível."), "warning")

        SO = self.env["sale.order"].sudo()
        bl_type = self.env.ref("documentos.doc_type_bl", raise_if_not_found=False)
        ecls = SO.search([("primavera_ecl_ref", "!=", False)])
        fixed = 0

        for so in ecls:
            partner = so.partner_id
            if not partner:
                continue
            updates = {}

            if not so.export_doc_type and partner.export_doc_type:
                updates["export_doc_type"] = partner.export_doc_type

            if not so.ecl_doc_line_ids and partner.required_doc_ids:
                assignee = partner.user_id
                doc_lines = []
                for doc in partner.required_doc_ids.sorted("sequence"):
                    if bl_type and doc.id == bl_type.id and assignee:
                        responsible = [(6, 0, assignee.ids)]
                    else:
                        responsible = [(6, 0, doc.responsible_ids.ids)]
                    doc_lines.append((0, 0, {
                        "doc_type_id": doc.id,
                        "responsible_ids": responsible,
                        "sequence": doc.sequence,
                    }))
                updates["ecl_doc_line_ids"] = doc_lines

            if updates:
                so.write(updates)
                fixed += 1

        msg = _("%s ECL(s) actualizados com dados do parceiro.") % fixed
        self._log("ecls", "success", msg)
        return self._notify(_("Reparar ECLs"), msg)

    def action_sync_all(self):
        for conn in self:
            conn._sync_all()
        return self._notify(_("Primavera"), _("Sincronização concluída."))

    def action_reset_ecl_counter(self):
        """Reinicia o contador de ECL para reimportar tudo."""
        self.ensure_one()
        self.ecl_last_imported_num = 0
        return self._notify(_("ECL"), _("Contador reiniciado. Próxima sincronização reimporta todas."))

    # ─────────────────────────────────────────────────────────────────────
    # ECLs ANULADAS NO PRIMAVERA
    # ─────────────────────────────────────────────────────────────────────

    def _get_ecl_stage_anulada(self):
        """Etapa 'Anulada' do kanban de ECLs; criada na primeira utilização."""
        stage = self.env.ref("primavera_connector.stage_ecl_anulada", raise_if_not_found=False)
        if stage:
            return stage
        Stage = self.env["export.ecl.stage"].sudo()
        last = Stage.search([], order="sequence desc", limit=1)
        stage = Stage.create({
            "name": "Anulada",
            "sequence": (last.sequence or 50) + 10,
            "fold": True,
        })
        self.env["ir.model.data"].sudo().create({
            "module": "primavera_connector",
            "name": "stage_ecl_anulada",
            "model": "export.ecl.stage",
            "res_id": stage.id,
            "noupdate": True,
        })
        return stage

    def _ecl_anulacao_info(self, ecl_name):
        """(data, utilizador, código, descrição) da anulação no Primavera, ou None."""
        _prefix, serie, num = ecl_name.split("/")
        sql_conn = self._sql_connection()
        if not sql_conn:
            return None
        try:
            with sql_conn.cursor() as cur:
                cur.execute(
                    "SELECT s.DataAnulacao, s.UtilizadorAnulacao, s.MotivoAnulacao, m.Descricao "
                    "FROM CabecDoc c JOIN CabecDocStatus s ON s.IdCabecDoc = c.Id "
                    "LEFT JOIN MotivosEstorno m ON m.Motivo = s.MotivoAnulacao "
                    "WHERE c.TipoDoc = 'ECL' AND c.Serie = %s AND c.NumDoc = %s",
                    (serie, int(num)),
                )
                return cur.fetchone()
        except Exception:
            return None
        finally:
            sql_conn.close()

    def _apply_ecl_anulada(self, so):
        """Cancela a SO e põe-na (e o export.ecl) na etapa 'Anulada'.
        ECLs listadas em primavera_connector.ecl_anulacao_ignorar ficam como estão."""
        ignorar = {
            x.strip() for x in (
                self.env["ir.config_parameter"].sudo()
                .get_param("primavera_connector.ecl_anulacao_ignorar") or ""
            ).split(",") if x.strip()
        }
        if so.primavera_ecl_ref in ignorar:
            return so
        stage = self._get_ecl_stage_anulada()
        if so.state == "cancel" and so.stage_id == stage:
            return so
        if any(m.state == "posted" for m in so.invoice_ids):
            msg = _("%s anulada no Primavera mas tem fatura emitida no Odoo — não foi cancelada.") % so.primavera_ecl_ref
            self._log("ecls", "error", msg)
            self._send_sync_failure_alert("ECL anulada com fatura emitida", Exception(msg))
            return so
        if so.state != "cancel":
            so.with_context(disable_cancel_warning=True).action_cancel()
        so.stage_id = stage
        info = self._ecl_anulacao_info(so.primavera_ecl_ref)
        if info:
            data_anul, utilizador, motivo, descricao = info
            nota = _("ECL anulada no Primavera em %(data)s por %(user)s — motivo: %(motivo)s %(desc)s.") % {
                "data": data_anul.strftime("%d/%m/%Y %H:%M") if data_anul else "?",
                "user": utilizador or "?",
                "motivo": motivo or "",
                "desc": descricao or "",
            }
        else:
            nota = _("ECL anulada no Primavera.")
        self._ecl_post_change(so, html.escape(nota))
        self._log("ecls", "success", f"[notificação] {so.primavera_ecl_ref}: {nota}")
        return so

    # ─────────────────────────────────────────────────────────────────────
    # NOTIFICAÇÕES DE ALTERAÇÕES DE ECL
    # ─────────────────────────────────────────────────────────────────────
    # Fase 1 (14/10/2026): notifica só os parceiros listados no parâmetro
    # _ECL_NOTIFY_PARAM (Gonçalo Simões), pelo sininho do Odoo. Notifica:
    # quantidade, artigo novo/removido, preço, cabeçalho (data, incoterm,
    # local, país, transitário), anulação e anulação desfeita. NÃO notifica
    # lotes/validades nem ECLs novas (decisão do user).
    _ECL_NOTIFY_PARAM = "primavera_connector.ecl_change_notify_partner_ids"
    _ECL_HEAD_FIELDS = [
        ("ecl_incoterm", "Incoterm"),
        ("ecl_incoterm_local", "Local do incoterm"),
        ("ecl_pais_destino_id", "País de destino"),
        ("ecl_transitario", "Transitário"),
    ]

    def _ecl_notify_partners(self):
        raw = self.env["ir.config_parameter"].sudo().get_param(self._ECL_NOTIFY_PARAM) or ""
        ids = [int(x) for x in raw.split(",") if x.strip().isdigit()]
        return self.env["res.partner"].sudo().browse(ids).exists()

    def _ecl_post_change(self, so, body_html):
        """Regista a alteração no histórico da ECL SEM avisar ninguém e envia uma
        notificação (sininho) só aos parceiros configurados. Não se usa
        message_post: os seguidores das encomendas estão inscritos nas notas
        internas e seriam todos avisados."""
        so._message_log(body=Markup(body_html))
        if self.env.context.get("ecl_verificacao"):
            return  # correcção da verificação diária: já vai no relatório
        partners = self._ecl_notify_partners()
        if partners:
            so.message_notify(
                partner_ids=partners.ids,
                subject=f"{so.primavera_ecl_ref or so.name} — {so.partner_id.name or ''}",
                body=Markup(body_html),
            )

    @staticmethod
    def _fmt_num(v, decimals=None):
        if decimals is None:
            s = f"{v:g}"
        else:
            s = f"{v:.{decimals}f}"
        return s.replace(".", ",")

    def _ecl_snapshot(self, so):
        lines = {}
        for l in so.order_line:
            if l.display_type or not l.product_id:
                continue
            k = l.product_id.default_code or l.product_id.display_name
            # compara-se pelo código; nos textos mostra-se a descrição (mais fácil de ler)
            d = lines.setdefault(k, {"qty": 0.0, "prices": set(), "name": l.product_id.name or k})
            d["qty"] += l.product_uom_qty
            d["prices"].add(round(l.price_unit, 4))
        head = {"Data": so.date_order.date() if so.date_order else False}
        for f, label in self._ECL_HEAD_FIELDS:
            v = so[f]
            head[label] = (v.display_name if hasattr(v, "_name") else v) or ""
        return {"lines": lines, "head": head}

    def _ecl_diff(self, before, after):
        out = []
        bl, al = before["lines"], after["lines"]
        for k in sorted(set(bl) | set(al)):
            b, a = bl.get(k), al.get(k)
            name = (a or b).get("name") or k
            if b and not a:
                out.append(f"Linha removida: {name} — {self._fmt_num(b['qty'])}")
            elif a and not b:
                out.append(f"Linha nova: {name} — {self._fmt_num(a['qty'])}")
            else:
                if abs(a["qty"] - b["qty"]) > 0.0001:
                    out.append(f"{name} — quantidade {self._fmt_num(b['qty'])} → {self._fmt_num(a['qty'])}")
                if a["prices"] != b["prices"]:
                    fmt = lambda s: " / ".join(self._fmt_num(p, 2) for p in sorted(s))
                    out.append(f"{name} — preço {fmt(b['prices'])} → {fmt(a['prices'])}")
        for label, bv in before["head"].items():
            av = after["head"].get(label)
            if (bv or "") != (av or ""):
                if label == "Data":
                    bv = bv.strftime("%d/%m/%Y") if bv else ""
                    av = av.strftime("%d/%m/%Y") if av else ""
                out.append(f"{label}: {bv or '(vazio)'} → {av or '(vazio)'}")
        return out

    def _ecl_notify_changes(self, so, before):
        if before is None:
            return
        diffs = self._ecl_diff(before, self._ecl_snapshot(so))
        if not diffs:
            return
        quando = fields.Datetime.context_timestamp(
            self.with_context(tz="Europe/Lisbon"), fields.Datetime.now()).strftime("%d/%m/%Y %H:%M")
        body = (
            f"<p><b>ECL alterada no Primavera</b> ({quando}):</p><ul>"
            + "".join(f"<li>{html.escape(d)}</li>" for d in diffs)
            + "</ul>"
        )
        self._ecl_post_change(so, body)
        self._log("ecls", "success", f"[notificação] {so.primavera_ecl_ref}: {len(diffs)} alteração(ões): " + "; ".join(diffs)[:400])

    def _ecl_notify_new(self, so):
        """Notificação de ECL nova (acrescentada à fase 1 a 14/10/2026)."""
        linhas = so.order_line.filtered(lambda l: l.product_id and not l.display_type)
        detalhe = "".join(
            f"<li>{html.escape(l.product_id.name or l.product_id.default_code or '')} — "
            f"{self._fmt_num(l.product_uom_qty)}</li>"
            for l in linhas[:15]
        )
        if len(linhas) > 15:
            detalhe += f"<li>… e mais {len(linhas) - 15} linha(s)</li>"
        extra = []
        if so.ecl_pais_destino_id:
            extra.append(f"País de destino: {html.escape(so.ecl_pais_destino_id.name)}")
        if so.ecl_incoterm:
            extra.append(f"Incoterm: {html.escape(so.ecl_incoterm)} {html.escape(so.ecl_incoterm_local or '')}".strip())
        body = (
            f"<p><b>Nova ECL no Primavera</b>: {html.escape(so.primavera_ecl_ref or so.name)} — "
            f"{html.escape(so.partner_id.name or '')}</p>"
            + (f"<p>{' · '.join(extra)}</p>" if extra else "")
            + (f"<ul>{detalhe}</ul>" if detalhe else "")
        )
        self._ecl_post_change(so, body)
        self._log("ecls", "success", f"[notificação] {so.primavera_ecl_ref}: nova ECL ({so.partner_id.name or ''})")

    @api.model
    def _cron_fim_fase1_notificacoes_ecl(self):
        """Notificação única no fim da fase 1 (21/10/2026): resumo da semana e
        convite para decidir a fase 2. Desliga o próprio cron no fim."""
        Log = self.env["primavera.sync.log"].sudo()
        desde = fields.Datetime.now() - timedelta(days=7)
        logs = Log.search([("operation", "=", "ecls"), ("message", "=like", "[notificação]%"),
                           ("create_date", ">=", desde)])
        anul = len(logs.filtered(lambda l: "anulada no Primavera" in l.message))
        react = len(logs.filtered(lambda l: "anulação desfeita" in l.message))
        novas = len(logs.filtered(lambda l: ": nova ECL" in l.message))
        alter = len(logs) - anul - react - novas
        dias = defaultdict(int)
        for l in logs:
            dias[fields.Date.to_string(l.create_date.date())] += 1
        por_dia = "".join(f"<li>{d}: {n}</li>" for d, n in sorted(dias.items())) or "<li>(nenhuma)</li>"
        body = (
            "<p><b>Fim da fase 1 das notificações de alterações de ECL.</b></p>"
            f"<p>Na última semana recebeste <b>{len(logs)}</b> notificações: {novas} de ECLs novas, "
            f"{alter} de alterações, {anul} de anulações e {react} de anulações desfeitas.</p>"
            f"<p>Por dia:</p><ul>{por_dia}</ul>"
            "<p>Está na altura de decidirmos a fase 2: quem passa a receber estas notificações e se "
            "mudamos algum tipo. Fala com o Claude para combinarmos.</p>"
        )
        partners = self.search([], limit=1)._ecl_notify_partners()
        if partners:
            partners[:1].message_notify(
                partner_ids=partners.ids,
                subject="Notificações de ECL: fim da fase 1",
                body=Markup(body),
            )
        crons = self.env["ir.cron"].sudo().search([("code", "like", "_cron_fim_fase1_notificacoes_ecl")])
        crons.write({"active": False})

    def _reactivate_ecl(self, so):
        """Anulação desfeita no Primavera: volta a rascunho e a 'Estado Novo'
        (o resto da sincronização reconfirma a SO e actualiza as linhas)."""
        if so.state == "cancel":
            so.action_draft()
        new_stage = self.env.ref("documentos.stage_ecl_new", raise_if_not_found=False)
        if new_stage:
            so.stage_id = new_stage
        self._ecl_post_change(so, html.escape(_("Anulação desfeita no Primavera — ECL reactivada.")))
        self._log("ecls", "success", _("[notificação] %s: anulação desfeita no Primavera, ECL reactivada.") % so.primavera_ecl_ref)

    def _resync_single_ecl(self, ecl_name):
        """Re-sincroniza UMA ECL específica do Primavera para o Odoo.
        Usado pelo botão na sale.order ou por crons de re-sync.
        ecl_name no formato 'ECL/<serie>/<num>'."""
        self.ensure_one()
        # Parse ECL/2026/271 → serie=2026, num=271
        parts = (ecl_name or '').split('/')
        if len(parts) != 3 or parts[0].upper() != 'ECL':
            return None
        serie, num = parts[1], parts[2]
        filial = self.api_filial or "000"
        ep = f"/v2/Vendas/Docs/Edita/{filial}/ECL/{serie}/{num}"
        data = self._edita(ep)
        if data is None or not data.get("Entidade"):
            return None

        entidade = data["Entidade"]
        Partner = self.env["res.partner"].sudo().with_context(active_test=False)
        partner = Partner.search([("primavera_customer_code", "=", entidade)], limit=1)
        if not partner:
            return None

        date_val = self._parse_date(data.get("Data") or data.get("DataDoc"))
        campos = {
            cu["Nome"]: cu.get("Valor")
            for cu in data.get("CamposUtil", [])
            if cu.get("Nome") and cu.get("Valor") not in (None, "")
        }
        incoterm_val = self._clean(campos.get("CDU_Incoterm"))
        incoterm_local_val = self._clean(campos.get("CDU_IncotermLocal"))
        pais_code = self._clean(campos.get("CDU_Pais"))
        pais_id = self._country_id(pais_code) if pais_code else False
        transitario_val = self._clean(campos.get("CDU_transitario"))

        return self._sync_ecl_sale_order(
            ecl_name, partner, date_val, data,
            incoterm_val, incoterm_local_val, pais_id, transitario_val,
        )

    # Re-sync de ECLs: verificação incremental (só as ECLs com alguma alteração
    # no Primavera desde a última vez, pelo contador de versões VersaoUltAct de
    # CabecDoc, CabecDocStatus e LinhasDoc — apanha linhas, lotes e anulações)
    # e uma volta completa por dia a partir das 02:00 (hora de Lisboa). Se o SQL
    # não estiver disponível, volta à volta completa de hora a hora.
    _ECL_FULL_RESYNC_HOUR = 2

    def _ecl_resync_key(self, name):
        return f"primavera_connector.ecl_resync.{self.id}.{name}"

    def _ecl_resync_domain(self):
        """ECLs em curso: tudo menos 'Fechado' (decisão do user: as fechadas
        não são actualizadas); as 'Anulada' entram para apanhar anulações desfeitas."""
        anulada = self.env.ref("primavera_connector.stage_ecl_anulada", raise_if_not_found=False)
        return [
            ("primavera_ecl_ref", "like", "ECL/%"),
            "|", ("stage_id.fold", "=", False),
            ("stage_id", "=", anulada.id if anulada else 0),
        ]

    def _changed_ecl_refs(self, since_hex):
        """(refs de ECLs alteradas desde a versão `since_hex`, nova versão em hex)
        ou None se o SQL Server não estiver disponível. Só leitura."""
        sql_conn = self._sql_connection()
        if not sql_conn:
            return None
        try:
            with sql_conn.cursor() as cur:
                cur.execute("SELECT @@DBTS")
                new_ver = bytes(cur.fetchone()[0])
                since = bytes.fromhex(since_hex)
                cur.execute(
                    "SELECT 'ECL/' + c.Serie + '/' + CAST(c.NumDoc AS varchar) "
                    "FROM CabecDoc c LEFT JOIN CabecDocStatus s ON s.IdCabecDoc = c.Id "
                    "WHERE c.TipoDoc = 'ECL' AND (c.VersaoUltAct > %s OR s.VersaoUltAct > %s "
                    "OR EXISTS (SELECT 1 FROM LinhasDoc l WHERE l.IdCabecDoc = c.Id AND l.VersaoUltAct > %s))",
                    (since, since, since),
                )
                refs = sorted({r[0] for r in cur.fetchall()})
            return refs, new_ver.hex()
        finally:
            sql_conn.close()

    def _primavera_db_version(self):
        sql_conn = self._sql_connection()
        if not sql_conn:
            return None
        try:
            with sql_conn.cursor() as cur:
                cur.execute("SELECT @@DBTS")
                return bytes(cur.fetchone()[0]).hex()
        finally:
            sql_conn.close()

    def _resync_ecls_full(self):
        """Volta completa: todas as ECLs em curso. Devolve nº actualizadas."""
        SO = self.env["sale.order"].sudo()
        updated = 0
        por_ano = defaultdict(int)
        for so in SO.search(self._ecl_resync_domain()):
            if self._resync_single_ecl(so.primavera_ecl_ref):
                updated += 1
                por_ano[so.primavera_ecl_ref.split("/")[1]] += 1
        detalhe = ", ".join(f"{a}: {n}" for a, n in sorted(por_ano.items()))
        self._log("ecls", "success", _("[completo] Re-sync %s ECL(s) em curso (%s).") % (updated, detalhe or "-"))
        return updated

    def _run_ecl_resync(self):
        self.ensure_one()
        ICP = self.env["ir.config_parameter"].sudo()
        k_ver, k_full = self._ecl_resync_key("version"), self._ecl_resync_key("last_full")
        now = fields.Datetime.now()
        lisboa = now.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Europe/Lisbon"))
        last_full = fields.Datetime.from_string(ICP.get_param(k_full)) if ICP.get_param(k_full) else None
        last_full_lisboa = (
            last_full.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Europe/Lisbon")) if last_full else None
        )
        version = ICP.get_param(k_ver)

        changed = None
        sql_err = None
        if version:
            try:
                changed = self._changed_ecl_refs(version)
                if changed is None:
                    sql_err = _("sem ligação ao SQL Server %s:%s") % (self.sql_host, self.sql_port or 1433)
            except Exception as exc:
                changed = None
                sql_err = str(exc)
            self._track_sql_health(sql_err)

        sql_ok = changed is not None
        full_due = (
            not version
            or not last_full_lisboa
            or (last_full_lisboa.date() < lisboa.date() and lisboa.hour >= self._ECL_FULL_RESYNC_HOUR)
        )
        if not sql_ok and version and last_full and now - last_full < timedelta(hours=1):
            return  # SQL em baixo: volta completa no máximo de hora a hora
        if full_due or not sql_ok:
            new_ver = None
            try:
                new_ver = self._primavera_db_version()
            except Exception:
                pass
            self._resync_ecls_full()
            ICP.set_param(k_full, fields.Datetime.to_string(now))
            if new_ver:
                ICP.set_param(k_ver, new_ver)
            # Verificação diária Odoo ↔ Primavera, logo a seguir à volta completa
            # (só na volta diária com SQL a funcionar; sem cron próprio).
            if full_due and sql_ok:
                try:
                    self._verify_ecls()
                except Exception as exc:
                    self._log("ecls", "error", _("[verificação] Erro: %s") % exc)
            return

        refs, new_ver = changed
        SO = self.env["sale.order"].sudo()
        alvo = SO.search(self._ecl_resync_domain() + [("primavera_ecl_ref", "in", refs)]) if refs else SO
        feitas = []
        for so in alvo:
            if self._resync_single_ecl(so.primavera_ecl_ref):
                feitas.append(so.primavera_ecl_ref)
        ICP.set_param(k_ver, new_ver)
        if feitas:
            self._log("ecls", "success", _("[incremental] %s ECL(s) alterada(s): %s") % (len(feitas), ", ".join(feitas)))

    # ── Alerta de ligação SQL ao Primavera em baixo ─────────────────────
    # Anti-spam: só avisa se a falha durar mais de 1 h; 1 email nessa altura,
    # 1 lembrete por cada 24 h que continue em baixo e 1 email quando voltar
    # (só se tiver havido aviso de falha). Estado em ir.config_parameter.
    _SQL_ALERT_EMAILS = ["goncalo.simoes@mirazeite.com", "pedro.santos@mirazeite.com"]
    _SQL_ALERT_AFTER = timedelta(hours=1)
    _SQL_ALERT_REMIND = timedelta(hours=24)

    def _sql_health_key(self, name):
        return f"primavera_connector.sql_health.{self.id}.{name}"

    def _send_sql_alert(self, subject, body_html):
        Mail = self.env["mail.mail"].sudo()
        for email in self._SQL_ALERT_EMAILS:
            Mail.create({
                "subject": subject,
                "body_html": body_html,
                "email_to": email,
                "auto_delete": True,
            }).send()

    @staticmethod
    def _fmt_duration(delta):
        mins = int(delta.total_seconds() // 60)
        if mins < 120:
            return f"{mins} min"
        horas = mins // 60
        return f"{horas} h" if horas < 48 else f"{horas // 24} dias e {horas % 24} h"

    def _track_sql_health(self, error):
        """Regista o estado da ligação SQL (error=None → OK) e envia alertas.
        Persiste o estado ANTES de enviar email, para não repetir avisos."""
        self.ensure_one()
        ICP = self.env["ir.config_parameter"].sudo()
        k_since, k_alert = self._sql_health_key("down_since"), self._sql_health_key("last_alert")
        now = fields.Datetime.now()
        since = ICP.get_param(k_since)
        last_alert = ICP.get_param(k_alert)
        subject = body = None

        if error is None:
            if not since:
                return
            down = now - fields.Datetime.from_string(since)
            ICP.set_param(k_since, False)
            ICP.set_param(k_alert, False)
            self._log("connection", "success", _("Ligação SQL ao Primavera voltou (esteve em baixo %s).") % self._fmt_duration(down))
            if last_alert:
                subject = f"[Primavera] Ligação SQL voltou a funcionar (esteve em baixo {self._fmt_duration(down)})"
                body = (
                    f"<p>A ligação de leitura ao SQL Server do Primavera <b>({self.sql_host})</b> voltou a funcionar.</p>"
                    f"<p>Esteve em baixo cerca de <b>{self._fmt_duration(down)}</b>. As alterações feitas no "
                    f"Primavera durante esse tempo vão ser apanhadas automaticamente nos próximos minutos.</p>"
                    f"<p>Ligação: {self.name}</p>"
                )
        else:
            if not since:
                ICP.set_param(k_since, fields.Datetime.to_string(now))
                self._log("connection", "error", _("Ligação SQL ao Primavera falhou: %s") % error)
                return
            down = now - fields.Datetime.from_string(since)
            if down < self._SQL_ALERT_AFTER:
                return
            if last_alert and now - fields.Datetime.from_string(last_alert) < self._SQL_ALERT_REMIND:
                return
            ICP.set_param(k_alert, fields.Datetime.to_string(now))
            lembrete = bool(last_alert)
            subject = (
                f"[Primavera] {'Lembrete: ' if lembrete else ''}ligação SQL em baixo há {self._fmt_duration(down)}"
            )
            body = (
                f"<p>A ligação de leitura ao SQL Server do Primavera <b>({self.sql_host})</b> está em baixo "
                f"há cerca de <b>{self._fmt_duration(down)}</b>.</p>"
                f"<p><b>Erro:</b> {html.escape(str(error))[:500]}</p>"
                f"<p>Enquanto durar: as alterações das ECLs chegam ao Odoo só de hora a hora (em vez de ~2 min), "
                f"e clientes/fornecedores voltam à revisão completa. A importação de ECLs e faturas novas "
                f"(pela WebAPI) não é afectada.</p>"
                f"<p>Receberás outro email quando a ligação voltar"
                f"{'' if lembrete else ', e no máximo um lembrete por dia enquanto continuar em baixo'}.</p>"
                f"<p>Ligação: {self.name}</p>"
            )
            self._log("connection", "error", _("Ligação SQL ao Primavera em baixo há %s: %s") % (self._fmt_duration(down), error))

        self.env.cr.commit()
        if subject:
            try:
                self._send_sql_alert(subject, body)
                self.env.cr.commit()
            except Exception as exc:
                self._log("connection", "error", f"Envio de email falhou: {exc}")
                self.env.cr.commit()

    # ── Verificação diária ECLs Odoo ↔ Primavera (ponto 6, 14/10/2026) ──
    # Corre logo a seguir à volta completa diária. Compara (só leitura no
    # Primavera) as ECLs das séries do ano corrente e anterior: em falta no
    # Odoo → importa (para 'Fechado' se fechada no Primavera); anulada não
    # reflectida → anula; em curso diferente → re-sincroniza; 'Fechado'
    # diferente ou só no Odoo → só reporta. Notifica os destinatários das
    # notificações de ECL só quando há alguma coisa.

    def _verify_ecls_primavera(self):
        hoje = fields.Date.context_today(self)
        # Série do ano corrente sempre; a do ano anterior só se o Odoo já tiver
        # ECLs dela (o Odoo começou em 2026 — não importar o histórico de 2025).
        anterior = str(hoje.year - 1)
        tem_anterior = self.env["sale.order"].sudo().search_count(
            [("primavera_ecl_ref", "like", f"ECL/{anterior}/%")], limit=1)
        series = (str(hoje.year), anterior if tem_anterior else str(hoje.year))
        prim = {}
        sql_conn = self._sql_connection()
        if not sql_conn:
            raise UserError(_("sem ligação ao SQL Server"))
        try:
            with sql_conn.cursor() as cur:
                cur.execute(
                    "SELECT 'ECL/' + c.Serie + '/' + CAST(c.NumDoc AS varchar), ISNULL(s.Anulado,0), ISNULL(s.Fechado,0), "
                    "c.Nome, c.CDU_Incoterm, c.CDU_IncotermLocal, c.CDU_transitario, c.CDU_Pais, c.Data "
                    "FROM CabecDoc c LEFT JOIN CabecDocStatus s ON s.IdCabecDoc = c.Id "
                    "WHERE c.TipoDoc = 'ECL' AND c.Serie IN (%s, %s)", series)
                for ref, anul, fech, nome, inc, loc, tr, pais, data in cur.fetchall():
                    prim[ref] = {
                        "anulada": bool(anul), "fechada": bool(fech), "nome": nome or "", "linhas": {}, "data": data,
                        "cab": {"incoterm": (inc or "").strip(), "local": (loc or "").strip(),
                                "transitário": (tr or "").strip(), "país": (pais or "").strip()},
                    }
                cur.execute(
                    "SELECT 'ECL/' + c.Serie + '/' + CAST(c.NumDoc AS varchar), l.Artigo, l.Quantidade, l.PrecUnit "
                    "FROM CabecDoc c JOIN LinhasDoc l ON l.IdCabecDoc = c.Id "
                    "WHERE c.TipoDoc = 'ECL' AND c.Serie IN (%s, %s) AND l.Artigo IS NOT NULL AND l.Artigo <> ''", series)
                for ref, art, q, p in cur.fetchall():
                    d = prim[ref]["linhas"].setdefault(art, [0.0, set()])
                    d[0] += float(q or 0)
                    d[1].add(round(float(p or 0), 2))
        finally:
            sql_conn.close()
        return prim, series

    def _verify_ecl_diffs(self, so, p):
        ol = {}
        for l in so.order_line:
            if l.product_id and not l.display_type:
                d = ol.setdefault(l.product_id.default_code, [0.0, set()])
                d[0] += l.product_uom_qty
                d[1].add(round(l.price_unit, 2))
        dif = []
        for k in sorted(set(ol) | set(p["linhas"])):
            a, b = p["linhas"].get(k), ol.get(k)
            if not a or not b:
                dif.append(f"artigo {k} só no {'Odoo' if b else 'Primavera'}")
            elif abs(a[0] - b[0]) > 0.001:
                dif.append(f"{k}: quantidade Primavera {self._fmt_num(a[0])} / Odoo {self._fmt_num(b[0])}")
            elif a[1] != b[1]:
                dif.append(f"{k}: preço diferente")
        cab_o = {"incoterm": so.ecl_incoterm or "", "local": so.ecl_incoterm_local or "",
                 "transitário": so.ecl_transitario or "", "país": so.ecl_pais_destino_id.code or ""}
        for k, v in p["cab"].items():
            if (v or "") != (cab_o[k] or "") and not (k == "país" and v and not cab_o[k]):
                dif.append(f"{k}: Primavera \"{v}\" / Odoo \"{cab_o[k]}\"")
        return dif

    def _verify_ecls(self):
        self.ensure_one()
        prim, series = self._verify_ecls_primavera()
        SO = self.env["sale.order"].sudo().with_context(active_test=False)
        odoo = {so.primavera_ecl_ref: so for so in SO.search([("primavera_ecl_ref", "like", "ECL/%")])}
        ignorar = {
            x.strip() for x in (self.env["ir.config_parameter"].sudo()
                                .get_param("primavera_connector.ecl_anulacao_ignorar") or "").split(",") if x.strip()
        }
        fechado = self.env.ref("documentos.stage_ecl_closed", raise_if_not_found=False)
        anulada_stage = self.env.ref("primavera_connector.stage_ecl_anulada", raise_if_not_found=False)
        me = self.with_context(ecl_verificacao=True)
        corrigido, atencao = [], []

        for ref, p in sorted(prim.items()):
            so = odoo.get(ref)
            if ref in ignorar:
                continue
            if not so:
                if p["anulada"]:
                    continue
                novo = me._resync_single_ecl(ref)
                if not novo:
                    atencao.append(f"{ref} — {p['nome']}: falta no Odoo e não foi possível importar (cliente em falta?)")
                    continue
                if p["data"] and (not novo.date_order or novo.date_order.date() != p["data"].date()):
                    novo.date_order = p["data"]
                destino = ""
                if p["fechada"] and fechado:
                    novo.stage_id = fechado
                    destino = " para \"Fechado\""
                corrigido.append(f"{ref} — {p['nome']}: faltava no Odoo; importada{destino}")
                continue
            if p["anulada"]:
                if so.state != "cancel":
                    me._resync_single_ecl(ref)
                    corrigido.append(f"{ref} — {p['nome']}: anulada no Primavera; anulada no Odoo")
                continue
            dif = self._verify_ecl_diffs(so, p)
            if not dif:
                continue
            em_fechado = so.stage_id.fold and so.stage_id != anulada_stage
            if em_fechado:
                atencao.append(f"{ref} — {p['nome']} (em \"Fechado\", não alterada): " + "; ".join(dif[:3]))
                continue
            me._resync_single_ecl(ref)
            so.invalidate_recordset()
            dif2 = self._verify_ecl_diffs(so, p)
            if dif2:
                atencao.append(f"{ref} — {p['nome']}: continua diferente após re-sincronizar: " + "; ".join(dif2[:3]))
            else:
                corrigido.append(f"{ref} — {p['nome']}: estava diferente ({'; '.join(dif[:2])}); corrigida")

        for ref, so in sorted(odoo.items()):
            if ref.split("/")[1] in series and ref not in prim:
                atencao.append(f"{ref}: existe no Odoo mas não no Primavera")

        resumo = _("[verificação] %s ECL(s) comparadas; %s corrigida(s); %s a precisar de atenção.") % (
            len(prim), len(corrigido), len(atencao))
        self._log("ecls", "success" if not atencao else "error", resumo + (" " + " | ".join(atencao))[:900] if atencao else resumo)
        # Avisos "a precisar de atenção" só são notificados uma vez (até mudarem)
        ICP = self.env["ir.config_parameter"].sudo()
        k_rep = f"primavera_connector.ecl_verif_reportados.{self.id}"
        ja = set(filter(None, (ICP.get_param(k_rep) or "").split("\n")))
        ICP.set_param(k_rep, "\n".join(sorted(atencao)) or False)
        atencao = [a for a in atencao if a not in ja]
        if not (corrigido or atencao):
            return
        quando = fields.Datetime.context_timestamp(
            self.with_context(tz="Europe/Lisbon"), fields.Datetime.now()).strftime("%d/%m/%Y %H:%M")
        body = f"<p><b>Verificação diária das ECLs</b> ({quando}) — {len(prim)} comparadas com o Primavera.</p>"
        if corrigido:
            body += "<p>Corrigido automaticamente:</p><ul>" + "".join(f"<li>{html.escape(x)}</li>" for x in corrigido) + "</ul>"
        if atencao:
            body += "<p><b>Precisa de atenção:</b></p><ul>" + "".join(f"<li>{html.escape(x)}</li>" for x in atencao) + "</ul>"
        partners = self._ecl_notify_partners()
        if partners:
            partners[:1].message_notify(
                partner_ids=partners.ids,
                subject=f"Verificação das ECLs: {len(corrigido)} corrigida(s), {len(atencao)} a ver",
                body=Markup(body),
            )

    @api.model
    def cron_resync_ecls_ano_corrente(self):
        """Cron de re-sync de ECLs (o nome mantém-se por compatibilidade):
        incremental a cada execução + volta completa diária. Ver _run_ecl_resync."""
        for conn in self.search([("active", "=", True), ("sync_ecls", "=", True)]):
            try:
                conn._run_ecl_resync()
            except Exception as e:
                conn._log("ecls", "error", _("Erro no re-sync: %s") % e)

    # ─────────────────────────────────────────────────────────────────────
    # SINCRONIZAÇÃO COMPLETA
    # ─────────────────────────────────────────────────────────────────────

    def _sync_all(self):
        self.ensure_one()
        messages = []
        try:
            if self.sync_customers:
                stats = self._import_partners("customer")
                messages.append(_("Clientes: %s") % self._stats_msg(stats))
            if self.sync_suppliers:
                stats = self._import_partners("supplier")
                messages.append(_("Fornecedores: %s") % self._stats_msg(stats))
            if self.sync_ecls:
                stats = self._import_ecls()
                messages.append(_("ECLs: %s") % self._stats_msg(stats))
            if self.sync_faturas:
                stats = self._import_faturas()
                messages.append(_("Faturas: %s") % self._stats_msg(stats))
            if self.sync_products:
                stats = self._sync_products_from_sql(full=True)
                messages.append(_("Artigos: %s") % (self._stats_msg(stats) if stats else _("sem ligação SQL")))
            if self.sync_employees:
                try:
                    stats = self._import_employees()
                    messages.append(_("Funcionários: %s") % self._stats_msg(stats))
                except Exception as exc:
                    messages.append(_("Funcionários: ERRO — %s") % exc)

            message = "\n".join(messages) or _("Nada para sincronizar.")
            self.write({
                "last_sync_date": fields.Datetime.now(),
                "last_sync_message": message,
            })
            self._log("sync_all", "success", message)
        except Exception as exc:
            message = _("Falha na sincronização: %s") % exc
            self.write({
                "last_sync_date": fields.Datetime.now(),
                "last_sync_message": message,
            })
            self._log("sync_all", "error", message)
            raise

    @api.model
    def cron_sync_active_connections(self):
        for conn in self.search([("active", "=", True)]):
            conn._sync_all()

    @api.model
    def cron_import_ecls_only(self):
        for conn in self.search([("active", "=", True), ("sync_ecls", "=", True)]):
            try:
                stats = conn._import_ecls()
                if stats["created"] or stats["updated"]:
                    conn._log("ecls", "success", conn._stats_msg(stats))
            except Exception as exc:
                conn._log("ecls", "error", str(exc))

    def _send_sync_failure_alert(self, operation_label, exc):
        """Envia email single-target para SYNC_FAILURE_ALERT_EMAIL quando um
        cron 'split' falha. Rate-limit: máximo 1 email por dia por operação
        (usa ir.config_parameter como flag). Independente de
        alert_email_recipients."""
        self.ensure_one()
        try:
            ICP = self.env["ir.config_parameter"].sudo()
            # slug do operation_label para chave estável
            slug = re.sub(r"[^a-z0-9]+", "_", operation_label.lower()).strip("_")
            key = f"primavera_connector.sync_failure_alert_last.{slug}"
            today_str = fields.Date.context_today(self).isoformat()
            last_sent = ICP.get_param(key)
            if last_sent == today_str:
                # Já enviado email desta operação hoje — silêncio até amanhã
                return
            subject = f"[Primavera] Falha no sync de {operation_label}"
            body = (
                f"<p>O cron de sincronização de <b>{operation_label}</b> "
                f"falhou na conexão <b>{html.escape(self.name or '')}</b>.</p>"
                f"<p><b>Erro:</b></p>"
                f"<pre style='background:#f4f4f4;padding:8px;border-radius:4px;"
                f"white-space:pre-wrap'>{html.escape(str(exc))}</pre>"
                f"<p>Consulta detalhes em Odoo → Primavera → Logs "
                f"(filtro operation = {operation_label}).</p>"
                f"<p><i>Este alerta é enviado no máximo uma vez por dia por "
                f"operação. Se o cron continuar a falhar, só receberás novo "
                f"aviso amanhã.</i></p>"
            )
            self.env["mail.mail"].sudo().create({
                "subject": subject,
                "body_html": body,
                "email_to": SYNC_FAILURE_ALERT_EMAIL,
                "auto_delete": True,
            }).send()
            ICP.set_param(key, today_str)
        except Exception:
            # Não deixar o email atrapalhar o rollback nem o log da falha original
            pass

    # Sync incremental de parceiros: entre voltas completas só se importam os
    # parceiros cuja DataUltimaActualizacao/DataCriacao no Primavera mudou desde
    # a última execução (SELECT only). A volta completa corre uma vez por dia, a
    # partir das 02h (hora do Primavera), e sempre que o SQL não esteja
    # disponível. Os marcadores guardam a hora do próprio Primavera, para evitar
    # diferenças de fuso horário.
    _PARTNER_SQL = {
        "customer": ("Clientes", "Cliente"),
        "supplier": ("Fornecedores", "Fornecedor"),
    }

    def _changed_partner_codes(self, partner_type, since):
        """Devolve (códigos alterados desde `since`, hora actual do Primavera)
        ou None se o SQL Server não estiver disponível."""
        table, key = self._PARTNER_SQL[partner_type]
        if partner_type == "customer":
            prefix = self.customer_code_prefix or "CL"
        else:
            prefix = self.supplier_code_prefix or "FO"
        sql_conn = self._sql_connection()
        if not sql_conn:
            return None
        try:
            with sql_conn.cursor() as cur:
                cur.execute("SELECT GETDATE()")
                now = cur.fetchone()[0]
                cur.execute(
                    f"SELECT {key} FROM {table} WHERE {key} LIKE %s "
                    f"AND (DataUltimaActualizacao >= %s OR DataCriacao >= %s) "
                    f"ORDER BY {key}",
                    (prefix + "%", since, since),
                )
                codes = [r[0].strip() for r in cur.fetchall() if r[0]]
            return codes, now
        finally:
            sql_conn.close()

    def _run_partner_sync(self, partner_type):
        """Escolhe entre volta completa e incremental. Devolve (stats, modo)."""
        self.ensure_one()
        ICP = self.env["ir.config_parameter"].sudo()
        key = f"primavera_connector.partner_sync.{self.id}.{partner_type}"
        last_inc = ICP.get_param(f"{key}.last_incremental")
        last_full = ICP.get_param(f"{key}.last_full")
        if last_inc:
            since = fields.Datetime.from_string(last_inc) - timedelta(minutes=10)
        else:
            since = datetime(1900, 1, 1)
        try:
            changed, now = self._changed_partner_codes(partner_type, since) or (None, None)
        except Exception:
            changed = now = None
        full = (
            now is None
            or not last_inc
            or not last_full
            or (fields.Datetime.from_string(last_full).date() < now.date() and now.hour >= 2)
        )
        stats = self._import_partners(partner_type, codes=None if full else changed)
        if now is not None:
            ICP.set_param(f"{key}.last_incremental", fields.Datetime.to_string(now))
            if full:
                ICP.set_param(f"{key}.last_full", fields.Datetime.to_string(now))
        mode = _("completo") if full else _("incremental, %s alterados") % len(changed)
        return stats, mode

    @api.model
    def cron_import_customers_only(self):
        for conn in self.search([("active", "=", True), ("sync_customers", "=", True)]):
            try:
                stats, mode = conn._run_partner_sync("customer")
                conn._log("customers", "success", f"[{mode}] {conn._stats_msg(stats)}")
            except Exception as exc:
                conn._log("customers", "error", str(exc))
                conn._send_sync_failure_alert("clientes", exc)

    @api.model
    def cron_import_suppliers_only(self):
        for conn in self.search([("active", "=", True), ("sync_suppliers", "=", True)]):
            try:
                stats, mode = conn._run_partner_sync("supplier")
                conn._log("suppliers", "success", f"[{mode}] {conn._stats_msg(stats)}")
            except Exception as exc:
                conn._log("suppliers", "error", str(exc))
                conn._send_sync_failure_alert("fornecedores", exc)

    @api.model
    def cron_import_products_only(self):
        for conn in self.search([("active", "=", True), ("sync_products", "=", True)]):
            try:
                stats, mode = conn._run_product_sync()
                # Sem SQL não há nada a fazer (o alerta de SQL em baixo já existe);
                # o incremental só fica no log quando muda alguma coisa.
                if stats and (mode != _("incremental") or stats["created"] or stats["updated"]):
                    conn._log("products", "success", f"[{mode}] {conn._stats_msg(stats)}")
            except Exception as exc:
                conn._log("products", "error", str(exc))
                conn._send_sync_failure_alert("artigos", exc)

    @api.model
    def cron_import_employees_only(self):
        for conn in self.search([("active", "=", True), ("sync_employees", "=", True)]):
            try:
                stats = conn._import_employees()
                if stats["created"] or stats["updated"]:
                    conn._log("employees", "success", conn._stats_msg(stats))
            except Exception as exc:
                conn._log("employees", "error", str(exc))

    @api.model
    def cron_import_faturas_only(self):
        for conn in self.search([("active", "=", True), ("sync_faturas", "=", True)]):
            try:
                stats_fa = conn._import_faturas()
                if stats_fa["created"] or stats_fa["updated"]:
                    conn._log("faturas", "success", conn._stats_msg(stats_fa))
            except Exception as exc:
                conn._log("faturas", "error", str(exc))

    # ─────────────────────────────────────────────────────────────────────
    # HEALTH CHECK / ALERTA API CAÍDA
    # ─────────────────────────────────────────────────────────────────────

    def _probe_api_once(self):
        """Uma tentativa. Devolve (ok, mensagem, is_transient)."""
        self.ensure_one()
        try:
            r = requests.get(
                f"{self.api_url}/v2/Inventario/Armazens/Existe/A1",
                headers=self._headers(),
                timeout=20,
            )
        except requests.Timeout:
            return False, f"Timeout a chamar {self.api_url}", True
        except requests.RequestException as exc:
            return False, f"Erro HTTP: {exc}", True
        except UserError as exc:
            return False, f"Autenticação falhou: {exc}", False
        # 409 = concorrência com outro cron (ERP Engine in use); tratar como transitório
        if r.status_code == 409:
            return False, f"HTTP 409: {r.text[:180]}", True
        if r.status_code >= 500:
            return False, f"HTTP {r.status_code}: {r.text[:180]}", True
        if r.status_code >= 400:
            return False, f"HTTP {r.status_code}: {r.text[:180]}", False
        try:
            body = r.json()
        except Exception:
            return False, f"Resposta não-JSON: {r.text[:180]}", False
        if body.get("StatusCode", 200) >= 400 or body.get("ErrorMessage"):
            return False, f"API devolveu erro: {body.get('ErrorMessage') or body}", False
        return True, "OK", False

    def _probe_api(self):
        """Probe robusto: 3 tentativas com backoff curto. Só falha se todas falharem."""
        import time
        last_msg = ""
        for attempt in range(3):
            ok, msg, transient = self._probe_api_once()
            if ok:
                return True, "OK"
            last_msg = msg
            if not transient:
                return False, msg
            if attempt < 2:
                time.sleep(2)
        return False, f"3 tentativas falharam. Último: {last_msg}"

    def _send_api_alert(self, subject, body_html):
        """Envia email para os destinatários configurados."""
        self.ensure_one()
        raw = self.alert_email_recipients or ""
        emails = [e.strip() for e in raw.replace(";", ",").split(",") if e.strip()]
        if not emails:
            return
        Mail = self.env["mail.mail"].sudo()
        for email in emails:
            Mail.create({
                "subject": subject,
                "body_html": body_html,
                "email_to": email,
                "auto_delete": True,
            }).send()

    # Anti-spam do alerta da WebAPI: falhas curtas só ficam no log; email só
    # quando a API está em baixo há mais de _API_ALERT_AFTER, um lembrete por
    # cada 24 h que continue em baixo e um email quando voltar (só se tiver
    # havido aviso). Logs com a operação 'connection' — o valor 'health' não
    # existe em primavera.sync.log e fazia o alerta rebentar antes do email.
    _API_ALERT_AFTER = timedelta(minutes=30)
    _API_ALERT_REMIND = timedelta(hours=24)

    def _run_health_check(self):
        """Corre health check e envia alertas com anti-spam.
        Persiste estado ANTES de enviar email (para não repetir se send crashar)."""
        self.ensure_one()
        ICP = self.env["ir.config_parameter"].sudo()
        k_alert = f"primavera_connector.api_health.{self.id}.last_alert"
        now = fields.Datetime.now()
        ok, msg = self._probe_api()
        last_alert = ICP.get_param(k_alert)

        vals = {"api_health_last_check": now, "api_health_last_message": msg}
        alert_subject = alert_body = None

        if ok:
            if not self.api_healthy:
                down = now - self.api_health_fail_since if self.api_health_fail_since else timedelta(0)
                vals.update({"api_healthy": True, "api_health_fail_since": False})
                self._log("connection", "success", f"WebAPI voltou a responder (esteve em baixo {self._fmt_duration(down)}).")
                if last_alert:
                    ICP.set_param(k_alert, False)
                    alert_subject = f"[Primavera] WebAPI voltou a responder (esteve em baixo {self._fmt_duration(down)})"
                    alert_body = (
                        f"<p>A WebAPI do Primavera <b>({self.api_url})</b> voltou a responder normalmente.</p>"
                        f"<p>Esteve em baixo cerca de <b>{self._fmt_duration(down)}</b>. As ECLs e faturas criadas "
                        f"entretanto vão entrar no Odoo nos próximos minutos.</p>"
                        f"<p>Ligação: {self.name}</p>"
                    )
        else:
            if self.api_healthy or not self.api_health_fail_since:
                vals.update({"api_healthy": False, "api_health_fail_since": now})
                self._log("connection", "error", f"WebAPI não responde: {msg}")
            else:
                down = now - self.api_health_fail_since
                remind_due = not last_alert or now - fields.Datetime.from_string(last_alert) >= self._API_ALERT_REMIND
                if down >= self._API_ALERT_AFTER and remind_due:
                    lembrete = bool(last_alert)
                    ICP.set_param(k_alert, fields.Datetime.to_string(now))
                    alert_subject = (
                        f"[Primavera] {'Lembrete: ' if lembrete else ''}WebAPI não responde há {self._fmt_duration(down)}"
                    )
                    alert_body = (
                        f"<p>A WebAPI do Primavera <b>({self.api_url})</b> não responde há cerca de "
                        f"<b>{self._fmt_duration(down)}</b>.</p>"
                        f"<p><b>Último erro:</b> {html.escape(str(msg))[:500]}</p>"
                        f"<p>Enquanto durar, as ECLs e faturas novas não entram no Odoo e as restantes "
                        f"sincronizações com o Primavera ficam paradas.</p>"
                        f"<p>Receberás outro email quando a WebAPI voltar"
                        f"{'' if lembrete else ', e no máximo um lembrete por dia enquanto continuar em baixo'}.</p>"
                        f"<p>Ligação: {self.name}</p>"
                    )
                    self._log("connection", "error",
                              f"WebAPI em baixo há {self._fmt_duration(down)} — aviso enviado: {msg}")

        # 1. Persistir estado + log ANTES de enviar email
        self.write(vals)
        self.env.cr.commit()

        # 2. Enviar email só depois do commit — se falhar, estado já está persistido
        if alert_subject:
            try:
                self._send_api_alert(alert_subject, alert_body)
                self.env.cr.commit()
            except Exception as exc:
                self._log("connection", "error", f"Envio de email falhou: {exc}")
                self.env.cr.commit()

    @api.model
    def cron_api_health_check(self):
        for conn in self.search([("active", "=", True)]):
            try:
                conn._run_health_check()
            except Exception as exc:
                conn._log("connection", "error", f"Health check da WebAPI crashou: {exc}")

    # ─────────────────────────────────────────────────────────────────────
    # IMPORTAÇÃO DE FUNCIONÁRIOS (WebAPI Primavera → hr.employee)
    # ─────────────────────────────────────────────────────────────────────

    # Lista conhecida de funcionários Primavera (fallback quando a API não tem endpoint RH)
    _KNOWN_EMPLOYEES = [
        ("009", "JOSE CARLOS DOS REIS PERDIGÃO"),
        ("012", "MARIA FERNANDA MARTINS LEAL D.PEREIRA"),
        ("013", "MARIA MANUELA DA FONSECA"),
        ("015", "PAULO JORGE DINIS TAVARES"),
        ("031", "CLÁUDIA PATRICIA PIRES ZACARIAS"),
        ("032", "JOSÉ CARLOS TEIXEIRA SIMÕES"),
        ("034", "MARIA DO CARMO DOS SANTOS ARSENIO"),
        ("037", "BRUNO MANUEL SIMOES CANINHAS"),
        ("041", "ELISABETE MORGADO HENRIQUES"),
        ("043", "ELISA DE AGUIAR PIRES DOS SANTOS"),
        ("045", "RUI MIGUEL MAIA LAMEIRA"),
        ("046", "FATIMA DE OLIVEIRA RAMOS"),
        ("047", "SUSANA CRISTINA DUARTE GERARDO"),
        ("052", "DORA ISABEL DUARTE GONÇALVES"),
        ("057", "TIAGO MIGUEL MARQUES BERNARDINO"),
        ("060", "MARIA FILIPA DE SOUSA ANTUNES DA CONCEIÇÃO"),
        ("063", "FÁBIO SÁ DE ARAÚJO"),
        ("069", "CARLOS ALEXANDRE SIMOES CANINHAS"),
        ("072", "JOÃO MIGUEL LUZ FERREIRA"),
        ("085", "GABRIEL ALEXANDRE GRAÇA MARTINHO"),
        ("089", "ANDRE LOPES REIS"),
        ("090", "FERNANDO JORGE DOS REIS SIMÕES"),
        ("095", "FILOMENA MARIA CARDO FURTADO SIMOES"),
        ("100", "FLORBELA CARVALHO MONIM GRAÇA LOPES"),
        ("112", "ALBANO EMANUEL MARQUES RIBEIRO"),
        ("124", "FERNANDA MARIA GENTIL COSTA GONÇALVES"),
        ("126", "THIAGO HENRIQUE ROSADO FREITAS"),
        ("131", "IMACULADA DA CONCEIÇÃO FAUSTO"),
        ("132", "RUI PEDRO GOMES DA SILVA"),
        ("133", "ADRIANA FILIPA JOURDAN CARROLINO"),
        ("138", "DAVID MANUEL PIEDADE SANTOS"),
        ("139", "BRUNA AZEVEDO LIMA CARVALHO JORGE"),
        ("141", "BRUNO SOARES DE SIQUEIRA"),
        ("142", "MARIA GUMERZINDA DE OLIVEIRA SILVA MADURO"),
        ("145", "CLAUDIA DA COSTA MENDES"),
        ("146", "NELSON MANUEL MILAGAIA SERRANO"),
        ("147", "MARIA EDUARDA NZUMBA EDUARDO"),
        ("148", "CARLA SOFIA PEREIRA PIRES CARIA"),
        ("151", "RUDÍ REIS COSTA"),
        ("152", "FLÁVIO MONTEIRO DOS SANTOS"),
        ("153", "MUHAMMAD GHUFRAN"),
        ("154", "TOMÁS PEREIRA NEVES"),
        ("155", "SUSANA ISABEL COELHO MILAGAIA"),
        ("156", "BIANCA JORGE DE SIQUEIRA"),
        ("157", "PEDRO SANTOS PEREIRA"),
        ("158", "RITA DA COSTA FAROLEIRA"),
    ]

    # Módulos WebAPI a tentar para o endpoint de empregados
    _EMPLOYEE_API_MODULES = ("RH", "Pessoal", "RecursosHumanos")

    def _find_employee_base_ep(self):
        """Descobre qual módulo WebAPI expõe o endpoint de empregados."""
        for module in self._EMPLOYEE_API_MODULES:
            ep = f"/v2/{module}/Empregados/Edita/009"
            result = self._api_get(ep)
            if result is not None:
                return f"/v2/{module}/Empregados"
        return None

    def _import_employees_from_known_list(self):
        """Cria/actualiza funcionários a partir da lista local quando a WebAPI não tem endpoint RH."""
        Employee = self.env["hr.employee"].sudo().with_context(active_test=False)
        stats = {"created": 0, "updated": 0, "skipped": 0}
        for code, name in self._KNOWN_EMPLOYEES:
            employee = Employee.search([("primavera_employee_code", "=", code)], limit=1)
            if employee:
                if employee.name != name:
                    employee.write({"name": name})
                    stats["updated"] += 1
                else:
                    stats["skipped"] += 1
            else:
                Employee.create({"name": name, "primavera_employee_code": code, "active": True})
                stats["created"] += 1
        return stats

    def _import_employees(self):
        """Importa funcionários para hr.employee — WebAPI se disponível, lista local como fallback."""
        self.ensure_one()
        stats = {"created": 0, "updated": 0, "skipped": 0}

        if "hr.employee" not in self.env:
            raise UserError(_("Módulo de Recursos Humanos (hr) não está instalado."))

        base_ep = self._find_employee_base_ep()
        if not base_ep:
            # WebAPI não suporta endpoint RH nesta versão — usar lista local
            stats = self._import_employees_from_known_list()
            self._log("employees", "success",
                      _("Lista local (API sem endpoint RH): ") + self._stats_msg(stats))
            return stats

        Employee = self.env["hr.employee"].sudo().with_context(active_test=False)
        Department = self.env["hr.department"].sudo()

        digits = self.employee_code_digits or 3
        max_num = self.employee_code_max or 200
        miss_stop = self.employee_miss_stop or 30
        consecutive_misses = 0

        for num in range(1, max_num + 1):
            code = str(num).zfill(digits)
            data = self._edita(f"{base_ep}/Edita/{code}")

            if data is None:
                consecutive_misses += 1
                if consecutive_misses >= miss_stop:
                    break
                continue

            consecutive_misses = 0

            nome_completo = self._clean(data.get("NomeCompleto"))
            if not nome_completo:
                nome = self._clean(data.get("Nome") or data.get("PrimeiroNome")) or ""
                apelido = self._clean(data.get("Apelido") or data.get("UltimoNome")) or ""
                nome_completo = " ".join(p for p in [nome, apelido] if p).strip()

            if not nome_completo:
                stats["skipped"] += 1
                continue

            active = not bool(data.get("AnulacaoEmpregado") or data.get("Anulado"))

            dept_id = False
            dept_code = self._clean(str(data.get("Departamento") or "").strip())
            if dept_code:
                dept = Department.search([("name", "=", dept_code)], limit=1)
                if not dept:
                    dept = Department.create({"name": dept_code})
                dept_id = dept.id

            job_title = self._clean(
                data.get("DescricaoFuncao") or data.get("Funcao") or data.get("Cargo")
            ) or False

            sexo = self._clean(data.get("Sexo") or data.get("Genero"))
            gender = False
            if sexo:
                gender = "male" if sexo.upper() in ("M", "H", "MASCULINO") else "female"

            birthday = self._parse_date(
                data.get("DataNascimento") or data.get("DataNasc")
            )

            vals = {
                "name": nome_completo,
                "primavera_employee_code": code,
                "active": active,
                "work_email": self._clean(
                    data.get("EmailProfissional") or data.get("Email")
                ) or False,
                "work_phone": self._clean(
                    data.get("TelefoneProfissional") or data.get("Telefone")
                ) or False,
                "mobile_phone": self._clean(
                    data.get("TelemovelProfissional") or data.get("Telemovel")
                ) or False,
                "job_title": job_title,
                "department_id": dept_id or False,
                "gender": gender or False,
                "birthday": birthday or False,
                "ssnid": self._clean(data.get("NumContribuinte")) or False,
                "sinid": self._clean(data.get("NISS")) or False,
                "identification_id": self._clean(
                    data.get("NumCC") or data.get("NumBI") or data.get("NumIdent")
                ) or False,
                "private_street": self._clean(data.get("Morada")) or False,
                "private_zip": self._clean(
                    data.get("CodigoPostal") or data.get("CodPostal")
                ) or False,
                "private_city": self._clean(data.get("Localidade")) or False,
                "private_country_id": self._country_id("PT"),
            }
            vals = {k: v for k, v in vals.items() if v not in (None, False, "")}
            vals["active"] = active

            employee = Employee.search([("primavera_employee_code", "=", code)], limit=1)
            if employee:
                employee.write(vals)
                stats["updated"] += 1
            else:
                Employee.create(vals)
                stats["created"] += 1

        self._log("employees", "success", self._stats_msg(stats))
        return stats

    # ─────────────────────────────────────────────────────────────────────
    # IMPORTAÇÃO DE PARCEIROS (Clientes / Fornecedores)
    # ─────────────────────────────────────────────────────────────────────

    def _import_partners(self, partner_type, codes=None):
        """Varre códigos sequencialmente e importa cada parceiro encontrado.
        Se `codes` for dado (sync incremental), processa só esses códigos."""
        self.ensure_one()
        if partner_type == "customer":
            prefix = self.customer_code_prefix or "CL"
            digits = self.customer_code_digits or 4
            max_num = self.customer_code_max or 999
            base_ep = "/v2/Base/Clientes"
            code_field = "primavera_customer_code"
            rank_field = "customer_rank"
            operation = "customers"
            category_xmlid = "primavera_connector.partner_category_primavera_customer"
        else:
            prefix = self.supplier_code_prefix or "FO"
            digits = self.supplier_code_digits or 4
            max_num = self.supplier_code_max or 999
            base_ep = "/v2/Base/Fornecedores"
            code_field = "primavera_supplier_code"
            rank_field = "supplier_rank"
            operation = "suppliers"
            category_xmlid = "primavera_connector.partner_category_primavera_supplier"

        stats = {"created": 0, "updated": 0, "skipped": 0}
        Partner = self.env["res.partner"].sudo().with_context(active_test=False)
        category = self.env.ref(category_xmlid)
        consecutive_misses = 0

        if codes is not None:
            scan = codes
        else:
            scan = (f"{prefix}{str(num).zfill(digits)}" for num in range(1, max_num + 1))

        for code in scan:
            if not self._exists(f"{base_ep}/Existe/{code}"):
                if codes is not None:
                    continue
                consecutive_misses += 1
                if consecutive_misses >= self.consecutive_misses_stop:
                    break
                continue

            consecutive_misses = 0
            data = self._edita(f"{base_ep}/Edita/{code}")
            if not data:
                stats["skipped"] += 1
                continue

            vals = self._partner_vals_from_api(
                data, partner_type, code_field, rank_field, category
            )
            if not vals:
                stats["skipped"] += 1
                continue

            partner = Partner.search([(code_field, "=", code)], limit=1)
            vat = vals.get("vat")
            if not partner and partner_type == "customer":
                partner = self._find_existing_partner(vat)

            if partner:
                if partner_type == "supplier" and partner.primavera_customer_code:
                    # Cliente que também é fornecedor: os dados do cliente mandam
                    # (nome, morada, telefone, ref…); aqui só se marca como fornecedor.
                    supplier_name = vals.get("name")
                    vals = {k: vals[k] for k in (code_field, rank_field, "category_id") if k in vals}
                    # Nome de fornecedor guardado à parte, para a pesquisa o encontrar
                    # (campo do módulo mirazeite_partner_search).
                    if "primavera_supplier_name" in partner._fields:
                        vals["primavera_supplier_name"] = (
                            supplier_name if supplier_name != partner.name else False
                        )
                self._safe_write_partner(partner, vals)
                stats["updated"] += 1
            else:
                self._safe_create_partner(Partner, vals)
                stats["created"] += 1

        self._log(operation, "success", self._stats_msg(stats))
        return stats

    def _sync_ecl_sale_order(self, ecl_name, partner, date_val, data,
                                  incoterm, incoterm_local, pais_id, transitario):
        """Cria ou actualiza o sale.order correspondente à ECL."""
        if "sale.order" not in self.env:
            return None

        SO = self.env["sale.order"].sudo()
        Product = self.env["product.product"].sudo().with_context(active_test=False)
        default_uom = self.env.ref("uom.product_uom_unit", raise_if_not_found=False)

        export_doc_type = partner.export_doc_type if partner else False

        so_vals = {
            "name": ecl_name,
            "partner_id": partner.id if partner else False,
            "date_order": date_val or fields.Datetime.now(),
            "primavera_ecl_ref": ecl_name,
            "export_doc_type": export_doc_type,
            "ecl_incoterm": incoterm,
            "ecl_incoterm_local": incoterm_local,
            "ecl_pais_destino_id": pais_id,
            "ecl_transitario": transitario,
        }
        so_vals = {k: v for k, v in so_vals.items() if v not in (None, False, "")}

        existing_so = SO.search([("primavera_ecl_ref", "=", ecl_name)], limit=1)

        # ECL anulada no Primavera: reflectir no Odoo sem mexer nas linhas
        if data.get("Anulado"):
            return self._apply_ecl_anulada(existing_so) if existing_so else None
        # Anulação desfeita no Primavera: reactivar antes de sincronizar
        anulada = self.env.ref("primavera_connector.stage_ecl_anulada", raise_if_not_found=False)
        if existing_so and anulada and existing_so.stage_id == anulada:
            self._reactivate_ecl(existing_so)
        # Fotografia antes da sincronização, para notificar o que mudou
        before = self._ecl_snapshot(existing_so) if existing_so else None

        # Linhas de produto da ECL
        linhas = data.get("Linhas") or []
        so_lines = []
        artigo_cache = {}

        # Mapa CodIva → TaxaIva, lido do cabeçalho ResumoIva. Permite aplicar
        # na linha a taxa exacta que Primavera atribui (0, 6, 13, 23 ou outras
        # regionais) e evita o Odoo aplicar o default 23% dos produtos.
        cod_to_rate = {}
        for r in (data.get("ResumoIva") or []):
            cod = r.get("CodIva")
            if cod is not None:
                cod_to_rate[cod] = r.get("TaxaIva") or 0.0
        AccountTax = self.env["account.tax"].sudo()

        for i, linha in enumerate(linhas):
            artigo = self._clean(linha.get("Artigo"))
            desc = self._clean(linha.get("Descricao") or linha.get("Descricao2")) or artigo or "—"
            qty = linha.get("Quantidade") or 1.0
            price = linha.get("PrecUnit") if linha.get("PrecUnit") is not None else 0.0
            lote = self._clean(linha.get("Lote"))
            if lote and lote.startswith('<') and lote.endswith('>'):
                lote = False
            unidade = self._clean(linha.get("Unidade")) or ""
            peso_liq = linha.get("IntrastatMassaLiq") or 0.0

            product = Product.search([("default_code", "=", artigo)], limit=1) if artigo else Product
            uom = (product.uom_id) if product else default_uom

            # Peso bruto / volume vêm do artigo
            if artigo and artigo not in artigo_cache:
                art_data = self._edita(f"/v2/Base/Artigos/Edita/{artigo}")
                artigo_cache[artigo] = {
                    "peso_bruto": art_data.get("Peso") or 0.0 if art_data else 0.0,
                    "volume":     art_data.get("Volume") or 0.0 if art_data else 0.0,
                }
            art_info = artigo_cache.get(artigo, {})

            line_vals = {
                "name": desc or "—",
                "product_uom_qty": qty or 1.0,
                "price_unit": price if price is not None else 0.0,
                "product_uom": uom.id if uom else False,
                "lote": lote or False,
                "peso_liquido": peso_liq,
                "peso_bruto": art_info.get("peso_bruto", 0.0),
                "volume": art_info.get("volume", 0.0),
                "caixas": int(qty) if unidade.upper() == "CX" else 0,
                "unidades_linha": qty,
            }
            if product:
                line_vals["product_id"] = product.id

            # Taxa IVA explícita conforme Primavera (ver cod_to_rate acima).
            # Força tax_id para não deixar Odoo aplicar o default do produto.
            cod_iva = linha.get("CodIva")
            rate = cod_to_rate.get(cod_iva, 0.0) if cod_iva else 0.0
            tax_ids = []
            if rate and rate > 0:
                tax = AccountTax.search([
                    ("type_tax_use", "=", "sale"),
                    ("amount", "=", rate),
                    ("price_include", "=", False),
                    ("name", "not ilike", "AZ"),
                    ("name", "not ilike", "MA"),
                ], limit=1)
                if tax:
                    tax_ids = tax.ids

            line_vals = {k: v for k, v in line_vals.items()
                         if v is not None and v is not False}
            line_vals.setdefault("price_unit", 0.0)
            line_vals.setdefault("product_uom_qty", 1.0)
            # tax_id aplicado SEMPRE (inclusive lista vazia) — tem de sobrepor
            # o default. Pôr depois do filtro que remove False.
            line_vals["tax_id"] = [(6, 0, tax_ids)]
            so_lines.append((0, 0, line_vals))

        if existing_so:
            update = {k: v for k, v in so_vals.items() if k != "partner_id"}
            # Campos de cabeçalho apagados no Primavera ficam vazios também no
            # Odoo (14/10/2026). Só se a API trouxe os campos de utilizador, para
            # não apagar por falta de dados; o país só é limpo se o código estiver
            # vazio (um código desconhecido mantém o país actual).
            if "CamposUtil" in data:
                cu = {c.get("Nome"): c.get("Valor") for c in (data.get("CamposUtil") or []) if c.get("Nome")}
                for campo, chave in (
                    ("ecl_incoterm", "CDU_Incoterm"),
                    ("ecl_incoterm_local", "CDU_IncotermLocal"),
                    ("ecl_transitario", "CDU_transitario"),
                    ("ecl_pais_destino_id", "CDU_Pais"),
                ):
                    if campo not in update and not self._clean(cu.get(chave)) and existing_so[campo]:
                        update[campo] = False
            # Atualizar linhas se a SO ainda não está bloqueada
            # (não tem faturas posted e não está em cancel/done) — Primavera é a fonte de verdade
            has_posted_invoice = any(
                m.state == 'posted' for m in existing_so.invoice_ids
            )
            updatable = (
                existing_so.state not in ("cancel", "done")
                and not has_posted_invoice
            )
            previous_state = existing_so.state
            if updatable and so_lines:
                # Voltar a draft temporariamente para permitir unlink das linhas
                if previous_state == "sale":
                    existing_so.with_context(disable_cancel_warning=True).action_cancel()
                    existing_so.action_draft()
                existing_so.order_line.unlink()
                update["order_line"] = so_lines
            if not existing_so.ecl_doc_line_ids and partner and partner.required_doc_ids:
                bl_type = self.env.ref(
                    'documentos.doc_type_bl', raise_if_not_found=False
                )
                assignee = partner.user_id
                doc_lines = []
                for doc in partner.required_doc_ids.sorted('sequence'):
                    if bl_type and doc.id == bl_type.id and assignee:
                        responsible = [(6, 0, assignee.ids)]
                    else:
                        responsible = [(6, 0, doc.responsible_ids.ids)]
                    doc_lines.append((0, 0, {
                        'doc_type_id': doc.id,
                        'responsible_ids': responsible,
                        'sequence': doc.sequence,
                    }))
                update["ecl_doc_line_ids"] = doc_lines
            existing_so.write(update)
            # Reconfirmar se estava em 'sale' antes do reset, ou se ainda está em 'draft'
            if previous_state == "sale" or existing_so.state == "draft":
                existing_so.write({"state": "sale"})
            self._ecl_notify_changes(existing_so, before)
            return existing_so
        else:
            if so_lines:
                so_vals["order_line"] = so_lines
            if not so_vals.get("partner_id"):
                return None
            so_vals["state"] = "sale"

            # Documentos de exportação — mesma lógica do export.ecl, com BL→assignee
            if partner and partner.required_doc_ids:
                bl_type = self.env.ref(
                    'documentos.doc_type_bl', raise_if_not_found=False
                )
                assignee = partner.user_id
                doc_lines = []
                for doc in partner.required_doc_ids.sorted('sequence'):
                    if bl_type and doc.id == bl_type.id and assignee:
                        responsible = [(6, 0, assignee.ids)]
                    else:
                        responsible = [(6, 0, doc.responsible_ids.ids)]
                    doc_lines.append((0, 0, {
                        'doc_type_id': doc.id,
                        'responsible_ids': responsible,
                        'sequence': doc.sequence,
                    }))
                so_vals["ecl_doc_line_ids"] = doc_lines

            new_so = SO.create(so_vals)
            self._ecl_notify_new(new_so)
            return new_so

    def _partner_vals_from_api(self, data, partner_type, code_field, rank_field, category):
        """Mapeia campos API Primavera → vals Odoo."""
        if partner_type == "customer":
            code = self._clean(data.get("Cliente"))
        else:
            code = self._clean(data.get("Fornecedor"))

        name = self._clean(data.get("NomeFiscal")) or self._clean(data.get("Nome"))
        if not code or not name:
            return None

        street = self._join_lines(data.get("Morada"), data.get("Morada1") or data.get("Morada2"))
        street2 = self._clean(data.get("Morada2")) if data.get("Morada1") else None
        vat = self._format_vat(data.get("NumContribuinte") or data.get("NumContrib"), data.get("Pais"))

        vals = {
            "name": name,
            "is_company": True,
            "company_type": "company",
            code_field: code,
            "ref": code,
            rank_field: 1,
            "street": street,
            "street2": street2,
            "city": self._clean(data.get("Localidade")) or self._clean(data.get("LocalidadeCodigoPostal")),
            "zip": self._clean(data.get("CodigoPostal") or data.get("Cp")),
            "phone": self._clean(data.get("Telefone") or data.get("Tel")),
            "mobile": self._clean(data.get("Telefone2")),
            "email": self._clean(data.get("Email")),
            "website": self._clean(data.get("EnderecoWeb")),
            "vat": vat,
            "country_id": self._country_id(data.get("Pais")),
            "active": not bool(data.get("ClienteAnulado") or data.get("FornecedorAnulado")),
            "comment": self._clean(data.get("Notas")),
            "category_id": [(4, category.id)],
        }
        return {k: v for k, v in vals.items() if v not in (None, False, "")}

    # ─────────────────────────────────────────────────────────────────────
    # IMPORTAÇÃO DE ECLs
    # ─────────────────────────────────────────────────────────────────────

    # ─────────────────────────────────────────────────────────────────────
    # MUDANÇA DE ANO DAS SÉRIES (ECL / FA / FAT)
    # ─────────────────────────────────────────────────────────────────────
    # As séries do Primavera são o ano (ex.: ECL/2026/…). Na primeira execução
    # de um ano novo, a série configurada passa para o ano corrente e o
    # contador recomeça; a série anterior continua a ser vigiada para
    # documentos atrasados até ao fim do mês _PREV_SERIES_UNTIL_MONTH.

    _SERIES_FIELDS = {
        "ECL": ("ecl_serie", "ecl_last_imported_num"),
        "FA": ("fa_serie", "fa_last_imported_num"),
        "FAT": ("fat_serie", "fat_last_imported_num"),
    }
    _PREV_SERIES_UNTIL_MONTH = 5  # vigiar a série do ano anterior até 31/05

    def _prev_series_key(self, doc_type):
        return f"primavera_connector.prev_serie.{self.id}.{doc_type}"

    def _check_series_rollover(self, doc_type):
        """Passa a série para o ano corrente se ainda estiver num ano anterior.
        Só actua em séries numéricas (ex.: '2026'); séries especiais ficam."""
        serie_f, last_f = self._SERIES_FIELDS[doc_type]
        today = fields.Date.context_today(self)
        old = (self[serie_f] or "").strip()
        if not (old.isdigit() and int(old) < today.year):
            return
        new = str(today.year)
        last = self[last_f] or 0
        self.env["ir.config_parameter"].sudo().set_param(
            self._prev_series_key(doc_type), f"{old}:{last}")
        self.write({serie_f: new, last_f: 0})
        self._log(
            "ecls" if doc_type == "ECL" else "faturas", "success",
            _("Mudança de ano: série %(t)s %(new)s iniciada. Série %(old)s continua vigiada "
              "até %(ate)s (última: %(t)s/%(old)s/%(last)s).") % {
                "t": doc_type, "new": new, "old": old, "last": last,
                "ate": f"{calendar.monthrange(today.year, self._PREV_SERIES_UNTIL_MONTH)[1]:02d}/"
                       f"{self._PREV_SERIES_UNTIL_MONTH:02d}/{today.year}",
            })

    def _prev_series(self, doc_type):
        """(série, último nº) do ano anterior se ainda estiver a ser vigiada."""
        today = fields.Date.context_today(self)
        if today.month > self._PREV_SERIES_UNTIL_MONTH:
            return None
        val = self.env["ir.config_parameter"].sudo().get_param(self._prev_series_key(doc_type)) or ""
        serie, _sep, last = val.partition(":")
        if serie != str(today.year - 1):
            return None
        return serie, int(last or 0)

    def _set_prev_series_last(self, doc_type, serie, last):
        self.env["ir.config_parameter"].sudo().set_param(
            self._prev_series_key(doc_type), f"{serie}:{last}")

    def _import_ecls(self):
        """Importa ECLs novas da série do ano corrente e, até 31/05, também da
        série do ano anterior (documentos atrasados)."""
        self.ensure_one()
        self._check_series_rollover("ECL")
        stats = self._import_ecls_serie()
        prev = self._prev_series("ECL")
        if prev:
            serie, last = prev
            stats_prev = self._import_ecls_serie(serie=serie, last_num=last)
            self._set_prev_series_last("ECL", serie, stats_prev.pop("_last"))
            for k in stats:
                stats[k] += stats_prev[k]
        return stats

    def _import_ecls_serie(self, serie=None, last_num=None):
        """Varre ECLs por número sequencial e importa-as como sale.order.
        Sem argumentos usa a série/contador configurados (e grava o contador);
        com `serie`/`last_num` (série anterior) devolve o último nº em stats['_last']."""
        self.ensure_one()
        current = serie is None

        if "export.ecl" not in self.env:
            return {"created": 0, "updated": 0, "skipped": 0, **({} if current else {"_last": last_num or 0})}

        stats = {"created": 0, "updated": 0, "skipped": 0}
        SO = self.env["sale.order"].sudo()
        Partner = self.env["res.partner"].sudo().with_context(active_test=False)

        if current:
            serie = self.ecl_serie or str(fields.Date.context_today(self).year)
            last_num = self.ecl_last_imported_num or 0
        filial = self.api_filial or "000"
        start = (last_num or 0) + 1
        max_num = self.ecl_scan_max or 500
        miss_stop = self.ecl_miss_stop or 50
        consecutive_misses = 0
        last_imported = last_num or 0

        for num in range(start, start + max_num):
            ep = f"/v2/Vendas/Docs/Edita/{filial}/ECL/{serie}/{num}"
            data = self._edita(ep)

            if data is None:
                # ECL não existe neste número
                consecutive_misses += 1
                if consecutive_misses >= miss_stop:
                    break
                continue

            # ECL existe na API — resetar misses e marcar como último encontrado
            consecutive_misses = 0
            last_imported = num

            if not data.get("Entidade"):
                stats["skipped"] += 1
                continue

            ecl_name = f"ECL/{serie}/{num}"
            entidade = data["Entidade"]

            existing_so = SO.search_count([("primavera_ecl_ref", "=", ecl_name)])

            # ECL que já chega anulada e ainda não existe no Odoo: não criar
            if data.get("Anulado") and not existing_so:
                stats["skipped"] += 1
                continue

            # Tentar encontrar o parceiro pelo código Primavera
            partner = Partner.search([("primavera_customer_code", "=", entidade)], limit=1)

            # Importar ou actualizar parceiro
            p_data = self._edita(f"/v2/Base/Clientes/Edita/{entidade}")
            if p_data:
                category = self.env.ref("primavera_connector.partner_category_primavera_customer")
                vals = self._partner_vals_from_api(
                    p_data, "customer", "primavera_customer_code", "customer_rank", category
                )
                if vals:
                    if not partner:
                        self._safe_create_partner(Partner, vals)
                        partner = Partner.search([("primavera_customer_code", "=", entidade)], limit=1)
                    elif not partner.ref:
                        # Parceiro existe mas sem ref (importado por versão anterior) — actualizar
                        self._safe_write_partner(partner, {"ref": entidade})

            if not partner:
                stats["skipped"] += 1
                continue

            date_val = self._parse_date(data.get("Data") or data.get("DataDoc"))
            campos = {
                cu["Nome"]: cu.get("Valor")
                for cu in data.get("CamposUtil", [])
                if cu.get("Nome") and cu.get("Valor") not in (None, "")
            }
            pais_code = self._clean(campos.get("CDU_Pais"))
            incoterm_val = self._clean(campos.get("CDU_Incoterm"))
            incoterm_local_val = self._clean(campos.get("CDU_IncotermLocal"))
            pais_id = self._country_id(pais_code) if pais_code else False
            transitario_val = self._clean(campos.get("CDU_transitario"))

            # A ECL no Odoo é a sale.order (kanban do Documentos); o antigo
            # registo export.ecl deixou de ser criado (14/10/2026).
            so = self._sync_ecl_sale_order(
                ecl_name, partner, date_val, data,
                incoterm_val, incoterm_local_val, pais_id, transitario_val,
            )
            if not so:
                stats["skipped"] += 1
            elif existing_so:
                stats["updated"] += 1
            else:
                stats["created"] += 1

        if not current:
            # Série do ano anterior: só registar quando houver novidades
            if stats["created"] or stats["updated"]:
                self._log("ecls", "success", f"[{serie}] {self._stats_msg(stats)}")
            stats["_last"] = last_imported
            return stats

        # Guardar último número importado
        if last_imported > (self.ecl_last_imported_num or 0):
            self.ecl_last_imported_num = last_imported

        self._log("ecls", "success", self._stats_msg(stats))
        return stats

    # ─────────────────────────────────────────────────────────────────────
    # IMPORTAÇÃO DE FATURAS (FA / FAT → account.move)
    # ─────────────────────────────────────────────────────────────────────

    def _import_faturas(self):
        """FA (+ FAT) da série do ano corrente e, até 31/05, da série anterior."""
        self.ensure_one()
        docs = [("FA", "fa_serie", "fa_last_imported_num", self.fa_scan_max, self.fa_miss_stop)]
        if self.sync_faturas_fat:
            docs.append(("FAT", "fat_serie", "fat_last_imported_num", self.fat_scan_max, self.fat_miss_stop))
        total = {"created": 0, "updated": 0, "skipped": 0}
        for doc_type, serie_f, last_f, scan_max, miss_stop in docs:
            self._check_series_rollover(doc_type)
            stats = self._import_faturas_doc(
                doc_type, self[serie_f], self[last_f], scan_max, miss_stop, last_f)
            prev = self._prev_series(doc_type)
            if prev:
                serie, last = prev
                stats_prev = self._import_faturas_doc(doc_type, serie, last, scan_max, miss_stop, None)
                self._set_prev_series_last(doc_type, serie, stats_prev.pop("_last"))
                for k in stats:
                    stats[k] += stats_prev[k]
            for k in total:
                total[k] += stats[k]
        return total

    def _import_faturas_doc(self, doc_type, serie, last_num, scan_max, miss_stop, counter_field):
        """Importa faturas de um tipo de documento para account.move."""
        self.ensure_one()
        stats = {"created": 0, "updated": 0, "skipped": 0}

        if "account.move" not in self.env:
            return stats

        AccountMove = self.env["account.move"].sudo()
        Partner = self.env["res.partner"].sudo().with_context(active_test=False)
        Product = self.env["product.product"].sudo().with_context(active_test=False)

        filial = self.api_filial or "000"
        serie = serie or "2026"
        start = (last_num or 0) + 1
        scan_max = scan_max or 500
        miss_stop = miss_stop or 50
        consecutive_misses = 0
        last_imported = last_num or 0

        # Journal de vendas para as facturas
        journal = self.env["account.journal"].sudo().search(
            [("type", "=", "sale")], limit=1
        )
        # Conta de rendimento por defeito para linhas sem produto
        default_account = self.env["account.account"].sudo().search(
            [("account_type", "in", ["income", "income_other"]),
             ("deprecated", "=", False)], limit=1
        )

        artigo_cache = {}  # artigo_code -> {peso_bruto, volume}

        # Pré-carrega TODOS os lotes do SQL Server numa única ligação
        lote_cache = {}   # (artigo, lote) -> data_validade | None
        sql_conn = self._sql_connection()
        if sql_conn:
            try:
                import datetime as _dt
                with sql_conn.cursor() as _cur:
                    _cur.execute("SELECT Artigo, Lote, Validade FROM dbo.ArtigoLote WHERE Validade IS NOT NULL")
                    for _row in _cur.fetchall():
                        if _row[2]:
                            _v = _row[2]
                            lote_cache[(_row[0], _row[1])] = (
                                _v.strftime('%Y-%m-%dT%H:%M:%S') if isinstance(_v, _dt.datetime) else str(_v)
                            )
            except Exception:
                pass
            finally:
                try:
                    sql_conn.close()
                except Exception:
                    pass

        for num in range(start, start + scan_max):
            ep = f"/v2/Vendas/Docs/Edita/{filial}/{doc_type}/{serie}/{num}"
            data = self._edita(ep)

            if data is None:
                consecutive_misses += 1
                if consecutive_misses >= miss_stop:
                    break
                continue

            consecutive_misses = 0
            last_imported = num

            if not data.get("Entidade"):
                stats["skipped"] += 1
                continue

            entidade = data["Entidade"]
            fatura_name = f"{doc_type}/{serie}/{num}"

            partner = Partner.search([("primavera_customer_code", "=", entidade)], limit=1)
            if not partner:
                p_data = self._edita(f"/v2/Base/Clientes/Edita/{entidade}")
                if p_data:
                    category = self.env.ref("primavera_connector.partner_category_primavera_customer")
                    vals = self._partner_vals_from_api(
                        p_data, "customer", "primavera_customer_code", "customer_rank", category
                    )
                    if vals:
                        self._safe_create_partner(Partner, vals)
                        partner = Partner.search([("primavera_customer_code", "=", entidade)], limit=1)

            date_val = self._parse_date(data.get("DataDoc") or data.get("Data"))

            # Campos utilizador do cabeçalho
            campos = {
                cu["Nome"]: cu.get("Valor")
                for cu in data.get("CamposUtil", [])
                if cu.get("Nome") and cu.get("Valor") not in (None, "")
            }

            pais_code = self._clean(campos.get("CDU_Pais")) or self._clean(data.get("Pais"))
            pais_id = self._country_id(pais_code) if pais_code else False

            move_vals = {
                "move_type": "out_invoice",
                "name": fatura_name,
                "partner_id": partner.id if partner else False,
                "invoice_date": date_val,
                "ref": fatura_name,
                "primavera_ref": fatura_name,
                "primavera_doc_type": doc_type,
                "primavera_serie": serie,
                "primavera_num": num,
                "primavera_filial": filial,
                "narration": self._clean(data.get("Observacoes")),
                "importador": self._clean(campos.get("CDU_CabVar1") or campos.get("CDU_Importador")),
                "distribuidor": self._clean(campos.get("CDU_CabVar2") or campos.get("CDU_Distribuidor")),
                "destino": self._clean(campos.get("CDU_CabVar3") or campos.get("CDU_Destino")),
                "modo_transporte": self._clean(campos.get("CDU_CabVar4") or campos.get("CDU_ModoTransporte")),
                "contentor": self._clean(campos.get("CDU_CabVar5") or campos.get("CDU_Contentor")),
                "ref_cliente": self._clean(
                    data.get("VossaRef") or data.get("VRef") or
                    data.get("RefCliente") or data.get("Referencia") or
                    data.get("Requisicao") or
                    campos.get("CDU_VossaRef") or campos.get("CDU_RefCliente")
                ),
                "pais_destino_id": pais_id,
            }
            if journal:
                move_vals["journal_id"] = journal.id
            move_vals = {k: v for k, v in move_vals.items() if v not in (None, False, "")}

            existing = AccountMove.search([("primavera_ref", "=", fatura_name)], limit=1)

            # Construir linhas
            linhas = data.get("Linhas") or []
            line_vals_list = []

            # Mapa CodIva → TaxaIva, lido do cabeçalho ResumoIva. Permite
            # aplicar na linha a taxa exacta do Primavera e evitar que o
            # Odoo aplique o default 23% dos produtos.
            cod_to_rate_inv = {}
            for r in (data.get("ResumoIva") or []):
                cod = r.get("CodIva")
                if cod is not None:
                    cod_to_rate_inv[cod] = r.get("TaxaIva") or 0.0
            AccountTax = self.env["account.tax"].sudo()

            for i, linha in enumerate(linhas):
                artigo = self._clean(linha.get("Artigo"))
                desc = self._clean(linha.get("Descricao") or linha.get("Descricao2")) or artigo or "—"
                qty = linha.get("Quantidade") or 0.0
                price = linha.get("PrecUnit") or linha.get("Preco") or 0.0
                lote = self._clean(linha.get("Lote"))
                if lote and lote.startswith('<') and lote.endswith('>'):
                    lote = False
                peso_liq = linha.get("IntrastatMassaLiq") or 0.0
                unidade = self._clean(linha.get("Unidade")) or ""

                # Peso bruto e volume: vai buscar ao artigo (com cache)
                if artigo and artigo not in artigo_cache:
                    art_data = self._edita(f"/v2/Base/Artigos/Edita/{artigo}")
                    artigo_cache[artigo] = {
                        "peso_bruto": art_data.get("Peso") or 0.0 if art_data else 0.0,
                        "volume": art_data.get("Volume") or 0.0 if art_data else 0.0,
                    }
                art_info = artigo_cache.get(artigo, {})

                # Validade: já pré-carregada do SQL Server; fallback individual se cache vazio
                data_val_raw = None
                if artigo and lote:
                    _key = (artigo, lote)
                    if _key not in lote_cache:
                        lote_cache[_key] = self._lote_data_validade(filial, artigo, lote)
                    data_val_raw = lote_cache[_key]

                product = Product.search([("default_code", "=", artigo)], limit=1) if artigo else Product

                lv = {
                    "name": desc,
                    "quantity": qty,
                    "price_unit": price,
                    "lote": lote or False,
                    "peso_liquido": peso_liq,
                    "peso_bruto": art_info.get("peso_bruto", 0.0),
                    "volume": art_info.get("volume", 0.0),
                    "data_validade": self._parse_date(data_val_raw) if data_val_raw else False,
                    "caixas": int(qty) if unidade.upper() == "CX" else 0,
                    "unidades_linha": qty,
                }
                if product:
                    lv["product_id"] = product.id
                elif default_account:
                    lv["account_id"] = default_account.id

                # CamposUtil da linha
                for cu in linha.get("CamposUtil", []):
                    nome = cu.get("Nome", "")
                    val = cu.get("Valor")
                    if val not in (None, ""):
                        if nome == "CDU_QuantidadeAlternativa":
                            lv["unidades_linha"] = val or lv["unidades_linha"]
                        elif nome in ("CDU_DataValidade", "CDU_Validade"):
                            lv["data_validade"] = self._parse_date(val)
                        elif nome == "CDU_Palete":
                            pass  # ignorar por agora

                # Taxa IVA explícita conforme Primavera (ver cod_to_rate_inv
                # acima). account.move.line usa 'tax_ids' (plural).
                cod_iva = linha.get("CodIva")
                rate = cod_to_rate_inv.get(cod_iva, 0.0) if cod_iva else 0.0
                tax_ids_val = []
                if rate and rate > 0:
                    tax = AccountTax.search([
                        ("type_tax_use", "=", "sale"),
                        ("amount", "=", rate),
                        ("price_include", "=", False),
                        ("name", "not ilike", "AZ"),
                        ("name", "not ilike", "MA"),
                    ], limit=1)
                    if tax:
                        tax_ids_val = tax.ids

                lv = {k: v for k, v in lv.items() if v not in (None, False, "")}
                # tax_ids aplicado SEMPRE (inclusive lista vazia) para
                # sobrepor o default do produto. Deve ir depois do filtro
                # que remove False.
                lv["tax_ids"] = [(6, 0, tax_ids_val)]
                line_vals_list.append((0, 0, lv))

            # ── Documentos de origem ───────────────────────────────────────
            origens = self._extrair_docs_origem(data, linhas)
            if origens:
                move_vals["primavera_docs_origem"] = ", ".join(origens)

            # Campos de cabeçalho que são seguros actualizar mesmo em faturas posted
            _SAFE_HEADER = {
                'importador', 'distribuidor', 'destino', 'modo_transporte',
                'contentor', 'pais_destino_id', 'ref_cliente',
                'narration', 'primavera_docs_origem',
            }

            if existing:
                if existing.state == "draft":
                    existing.invoice_line_ids.unlink()
                    update_vals = {k: v for k, v in move_vals.items()
                                   if k not in ("move_type", "journal_id")}
                    update_vals["invoice_line_ids"] = line_vals_list
                    existing.write(update_vals)
                else:
                    # Fatura já contabilizada: actualiza apenas campos que não afectam contabilidade
                    header_update = {k: v for k, v in move_vals.items() if k in _SAFE_HEADER}
                    if header_update:
                        existing.write(header_update)
                stats["updated"] += 1
                target_move = existing
            else:
                move_vals["invoice_line_ids"] = line_vals_list
                target_move = AccountMove.create(move_vals)
                stats["created"] += 1

            # ── Ligar a ECL e criar todos ──────────────────────────────────
            if origens:
                self._link_fatura_to_ecl(target_move, fatura_name, origens)

        if not counter_field:
            # Série do ano anterior: contador guardado por quem chama
            if stats["created"] or stats["updated"]:
                self._log("faturas", "success", f"[{doc_type}/{serie}] {self._stats_msg(stats)}")
            stats["_last"] = last_imported
            return stats

        if last_imported > (last_num or 0):
            self.write({counter_field: last_imported})

        self._log("faturas", "success", self._stats_msg(stats))
        return stats

    # ─────────────────────────────────────────────────────────────────────
    # IMPORTAÇÃO DE ARTIGOS (SQL do Primavera, só leitura)
    # ─────────────────────────────────────────────────────────────────────

    # Desde 26/10/2026 os artigos vêm directamente da tabela Artigo do Primavera
    # (só SELECT): a WebAPI não tem listagem e varrer as ECLs só apanhava os
    # artigos vendidos. Incremental pelo contador VersaoUltAct (muda com qualquer
    # alteração ao artigo, incluindo anulação) e volta completa uma vez por dia a
    # partir das 02:00 (hora de Lisboa). Só grava o que estiver diferente; nunca
    # apaga (anulado no Primavera → arquivado no Odoo). Sem SQL não faz nada.
    _PRODUCT_FULL_SYNC_HOUR = 2
    _PRODUCT_SKIP_CODES = {"TESTE57"}  # artigo de teste do Primavera (decisão do user)
    _PRODUCT_SQL_COLUMNS = (
        "Artigo, Descricao, ArtigoAnulado, UnidadeBase, UnidadeVenda, UnidadeCompra, "
        "Peso, Volume, CodBarras, Observacoes"
    )

    def _product_sync_key(self, name):
        return f"primavera_connector.product_sync.{self.id}.{name}"

    def _fetch_sql_products(self, since_hex=None):
        """(linhas da tabela Artigo como dicts, versão actual em hex), só os
        alterados depois de `since_hex` se for dado. None sem SQL. Só leitura."""
        sql_conn = self._sql_connection()
        if not sql_conn:
            return None
        try:
            with sql_conn.cursor() as cur:
                # Versão lida ANTES dos artigos: uma alteração feita entretanto
                # volta a ser apanhada na execução seguinte.
                cur.execute("SELECT @@DBTS")
                new_ver = bytes(cur.fetchone()[0]).hex()
                query = f"SELECT {self._PRODUCT_SQL_COLUMNS} FROM Artigo"
                params = ()
                if since_hex:
                    query += " WHERE VersaoUltAct > %s"
                    params = (bytes.fromhex(since_hex),)
                cur.execute(query, params)
                cols = [d[0] for d in cur.description]
                rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            return rows, new_ver
        finally:
            sql_conn.close()

    def _product_vals_from_sql(self, row, product):
        code = self._clean(row["Artigo"])
        uom_venda = self._get_or_create_uom(row["UnidadeVenda"] or row["UnidadeBase"])
        uom_compra = self._get_or_create_uom(row["UnidadeCompra"] or row["UnidadeBase"])
        vals = {
            "name": self._clean(row["Descricao"]),
            "default_code": code,
            "primavera_code": code,
            "active": not row["ArtigoAnulado"],
            "weight": row["Peso"] or 0.0,
            "volume": row["Volume"] or 0.0,
        }
        if uom_venda:
            vals["uom_id"] = uom_venda.id
            # O Odoo exige compra e venda na mesma categoria (ex.: MP.* vendem-se
            # em LT e compram-se em KG no Primavera) — nesse caso compra = venda.
            if not uom_compra or uom_compra.category_id != uom_venda.category_id:
                uom_compra = uom_venda
            vals["uom_po_id"] = uom_compra.id
        barcode = self._clean(row["CodBarras"])
        if barcode and self._barcode_available(barcode, product):
            vals["barcode"] = barcode
        observations = self._clean(row["Observacoes"])
        if observations:
            vals["description"] = observations
        return vals

    @staticmethod
    def _product_changed_vals(product, vals):
        """Só os campos que mudam (compara com a precisão do próprio campo)."""
        changed = {}
        for fname, value in vals.items():
            field = product._fields[fname]
            current = product[fname]
            if field.type == "many2one":
                current = current.id
            elif field.type == "float":
                if float_compare(current or 0.0, value or 0.0, precision_digits=field.get_digits(product.env)[1]) == 0:
                    continue
            elif fname == "description":
                current = html2plaintext(current or "").strip()
            if field.type != "float" and (current or False) == (value or False):
                continue
            changed[fname] = value
        return changed

    def _sync_products_from_sql(self, full=True):
        """Importa/actualiza artigos a partir do SQL do Primavera. Devolve stats
        ou None se o SQL não estiver disponível."""
        self.ensure_one()
        ICP = self.env["ir.config_parameter"].sudo()
        k_ver = self._product_sync_key("version")
        since = None if full else ICP.get_param(k_ver)
        fetched = self._fetch_sql_products(since)
        if fetched is None:
            return None
        rows, new_ver = fetched

        stats = {"created": 0, "updated": 0, "skipped": 0}
        Product = self.env["product.template"].sudo().with_context(active_test=False, lang="en_US")
        codes = [self._clean(r["Artigo"]) for r in rows]
        existing = {p.primavera_code: p for p in Product.search([("primavera_code", "in", codes)])}
        errors = []
        for row in rows:
            code = self._clean(row["Artigo"])
            if not code or code in self._PRODUCT_SKIP_CODES or not self._clean(row["Descricao"]):
                stats["skipped"] += 1
                continue
            product = existing.get(code)
            try:
                with self.env.cr.savepoint():
                    vals = self._product_vals_from_sql(row, product)
                    if product:
                        changed = self._product_changed_vals(product, vals)
                        if changed:
                            product.write(changed)
                            stats["updated"] += 1
                    else:
                        vals.update({"sale_ok": True, "purchase_ok": True})
                        Product.create(vals)
                        stats["created"] += 1
            except Exception as exc:
                stats["skipped"] += 1
                errors.append(f"{code}: {exc}")
        ICP.set_param(k_ver, new_ver)
        if full:
            ICP.set_param(self._product_sync_key("last_full"), fields.Datetime.to_string(fields.Datetime.now()))
        if errors:
            self._log("products", "error", _("Artigos com erro (%s): %s") % (len(errors), "; ".join(errors[:20])))
        return stats

    def _run_product_sync(self):
        """Escolhe entre volta completa e incremental. Devolve (stats, modo) ou
        (None, None) se o SQL não estiver disponível."""
        self.ensure_one()
        ICP = self.env["ir.config_parameter"].sudo()
        last_full = ICP.get_param(self._product_sync_key("last_full"))
        lisboa = datetime.now(ZoneInfo("Europe/Lisbon"))
        last_full_lisboa = (
            fields.Datetime.from_string(last_full).replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Europe/Lisbon"))
            if last_full else None
        )
        full = (
            not ICP.get_param(self._product_sync_key("version"))
            or not last_full_lisboa
            or (last_full_lisboa.date() < lisboa.date() and lisboa.hour >= self._PRODUCT_FULL_SYNC_HOUR)
        )
        stats = self._sync_products_from_sql(full=full)
        return stats, (_("completo") if full else _("incremental"))

    # ─────────────────────────────────────────────────────────────────────
    # UNIDADES DE MEDIDA
    # ─────────────────────────────────────────────────────────────────────

    # Mapeamento de códigos Primavera → XML id Odoo (fallback: criar na categoria Unit)
    _UOM_MAP = {
        'UN':  'uom.product_uom_unit',
        'UNI': 'uom.product_uom_unit',
        'L':   'uom.product_uom_litre',
        'LT':  'uom.product_uom_litre',
        'KG':  'uom.product_uom_kgm',
        'G':   'uom.product_uom_gram',
        'T':   'uom.product_uom_ton',
        'M':   'uom.product_uom_meter',
        'M2':  'uom.product_uom_square_meter',
        'M3':  'uom.product_uom_cubic_meter',
        'H':   'uom.product_uom_hour',
        'D':   'uom.product_uom_day',
    }

    def _get_or_create_uom(self, code):
        """Devolve uom.uom para o código Primavera, criando se necessário."""
        if not code:
            return self.env['uom.uom']
        code_upper = code.strip().upper()
        xml_id = self._UOM_MAP.get(code_upper)
        if xml_id:
            uom = self.env.ref(xml_id, raise_if_not_found=False)
            if uom:
                return uom
        # Procurar pelo nome
        uom = self.env['uom.uom'].sudo().search([('name', '=ilike', code_upper)], limit=1)
        if uom:
            return uom
        # Criar na categoria Unit
        cat_unit = self.env.ref('uom.product_uom_categ_unit', raise_if_not_found=False)
        if not cat_unit:
            cat_unit = self.env['uom.category'].sudo().search([('name', '=', 'Unit')], limit=1)
        if not cat_unit:
            return self.env['uom.uom']
        return self.env['uom.uom'].sudo().create({
            'name': code_upper,
            'category_id': cat_unit.id,
            'uom_type': 'bigger',
            'factor': 1.0,
        })

    # ─────────────────────────────────────────────────────────────────────
    # UTILIDADES DE PARCEIROS
    # ─────────────────────────────────────────────────────────────────────

    def _find_existing_partner(self, vat):
        if not vat:
            return self.env["res.partner"]
        partners = (
            self.env["res.partner"]
            .sudo()
            .with_context(active_test=False)
            .search([("vat", "=", vat)])
        )
        partners = partners.filtered(self._can_reuse_partner)
        return partners if len(partners) == 1 else self.env["res.partner"]

    def _can_reuse_partner(self, partner):
        if self.env["res.users"].sudo().search_count([("partner_id", "=", partner.id)]):
            return False
        if self.env["crm.lead"].sudo().search_count([("partner_id", "=", partner.id)]):
            return False
        return True

    def _safe_create_partner(self, Partner, vals):
        try:
            with self.env.cr.savepoint():
                Partner.create(vals)
            return False
        except ValidationError:
            if not vals.get("vat"):
                raise
            retry = self._vals_without_vat(vals)
            with self.env.cr.savepoint():
                Partner.create(retry)
            return True

    def _safe_write_partner(self, partner, vals):
        try:
            with self.env.cr.savepoint():
                partner.write(vals)
            return False
        except ValidationError:
            if not vals.get("vat"):
                raise
            retry = self._vals_without_vat(vals)
            with self.env.cr.savepoint():
                partner.write(retry)
            return True

    def _vals_without_vat(self, vals):
        retry = dict(vals)
        bad_vat = retry.pop("vat", False)
        if bad_vat:
            note = _("NIF/VAT Primavera não importado (falhou validação Odoo): %s") % bad_vat
            retry["comment"] = self._join_lines(retry.get("comment"), note)
        return retry

    def action_tag_existing_crm_contacts(self):
        self.ensure_one()
        category = self.env.ref("primavera_connector.partner_category_crm_prospect")
        leads = self.env["crm.lead"].sudo().search([("partner_id", "!=", False)])
        leads.mapped("partner_id").write({"category_id": [(4, category.id)]})
        message = _("Contactos CRM marcados: %s.") % len(leads)
        self._log("customers", "success", message)
        return self._notify(_("Contactos CRM"), message)

    def action_tag_odoo_user_contacts(self):
        self.ensure_one()
        category = self.env.ref("primavera_connector.partner_category_odoo_user")
        partners = self.env["res.users"].sudo().search([]).mapped("partner_id")
        partners.write({"category_id": [(4, category.id)]})
        message = _("Utilizadores Odoo marcados: %s.") % len(partners)
        self._log("customers", "success", message)
        return self._notify(_("Utilizadores Odoo"), message)

    # ─────────────────────────────────────────────────────────────────────
    # HELPERS GERAIS
    # ─────────────────────────────────────────────────────────────────────

    def _sql_connection(self):
        """Devolve uma ligação pymssql ao SQL Server do Primavera, ou None se não disponível."""
        if not (self.sql_host and self.sql_database and self.sql_user and self.sql_password):
            return None
        try:
            import pymssql
            return pymssql.connect(
                server=self.sql_host,
                port=self.sql_port or 1433,
                user=self.sql_user,
                password=self.sql_password,
                database=self.sql_database,
                timeout=5,
                login_timeout=5,
            )
        except Exception:
            return None

    def _trace_ecl_via_sql(self, tipo_doc, serie, num_doc, max_depth=6):
        """Usa a tabela LinhasDocTrans do Primavera para traçar a cadeia
        TipoDoc/Serie/NumDoc → ECL origem.
        Devolve uma lista de refs ECL/YYYY/N únicas encontradas (lista vazia se não houver).
        """
        sql_conn = self._sql_connection()
        if not sql_conn:
            return []
        ecls = []
        seen_cabec = set()
        try:
            with sql_conn.cursor() as cur:
                # 1. Encontrar o IdCabecDoc do documento de partida
                cur.execute(
                    "SELECT Id FROM CabecDoc WHERE Tipodoc=%s AND Serie=%s AND NumDoc=%s",
                    (tipo_doc, serie, int(num_doc)),
                )
                row = cur.fetchone()
                if not row:
                    return []
                cabec_id = row[0]
                # 2. Recolher IDs das linhas dessa fatura
                cur.execute("SELECT Id FROM LinhasDoc WHERE IdCabecDoc=%s", (cabec_id,))
                linhas_ids = [r[0] for r in cur.fetchall()]
                # 3. BFS recursiva — para cada linha, seguir IdLinhasDocOrigem
                # Cuidado: NÃO eliminar cabecalhos visitados — uma FA pode ter
                # várias ECLs origem se houve consolidação (GR juntou várias).
                # Eliminamos apenas linhas já visitadas para evitar ciclos.
                seen_linhas = set()
                queue = [(lid, 0) for lid in linhas_ids]
                while queue:
                    linha_id, depth = queue.pop(0)
                    if depth >= max_depth or linha_id in seen_linhas:
                        continue
                    seen_linhas.add(linha_id)
                    cur.execute(
                        "SELECT IdLinhasDocOrigem FROM LinhasDocTrans WHERE IdLinhasDoc=%s",
                        (linha_id,),
                    )
                    for (orig_linha,) in cur.fetchall():
                        if orig_linha in seen_linhas:
                            continue
                        cur.execute("SELECT IdCabecDoc FROM LinhasDoc WHERE Id=%s", (orig_linha,))
                        r = cur.fetchone()
                        if not r:
                            continue
                        orig_cabec = r[0]
                        cur.execute(
                            "SELECT Tipodoc, Serie, NumDoc FROM CabecDoc WHERE Id=%s",
                            (orig_cabec,),
                        )
                        d = cur.fetchone()
                        if d and d[0] == 'ECL':
                            ref = f"ECL/{d[1]}/{d[2]}"
                            if ref not in ecls:
                                ecls.append(ref)
                        else:
                            # Continuar o trace recuando (mesmo que cabec já visto, podem haver outras linhas)
                            queue.append((orig_linha, depth + 1))
        except Exception:
            return ecls
        finally:
            try:
                sql_conn.close()
            except Exception:
                pass
        return ecls

    def _lote_data_validade(self, filial, artigo, lote):
        """Obtém a data de validade de um lote a partir de dbo.ArtigoLote via SQL Server."""
        sql_conn = self._sql_connection()
        if sql_conn:
            try:
                with sql_conn.cursor() as cur:
                    cur.execute(
                        "SELECT Validade FROM dbo.ArtigoLote WHERE Artigo=%s AND Lote=%s",
                        (artigo, lote),
                    )
                    row = cur.fetchone()
                    if row and row[0]:
                        import datetime
                        val = row[0]
                        if isinstance(val, datetime.datetime):
                            return val.strftime('%Y-%m-%dT%H:%M:%S')
                        return str(val)
            except Exception:
                pass
            finally:
                try:
                    sql_conn.close()
                except Exception:
                    pass
        return None

    def _extrair_docs_origem(self, data, linhas):
        """Extrai referências dos documentos de origem de uma fatura Primavera."""
        import re as _re
        origens = []

        def _ref(tipo, serie, num):
            tipo = self._clean(tipo)
            serie = self._clean(serie)
            num = num if num else None
            if tipo and serie and num:
                return f"{tipo}/{serie}/{num}"
            return None

        def _ecl_from_descricao(desc):
            """Extrai ref ECL/AAAA/NN da linha de texto gerada pelo Primavera na transformação.
            Ex: 'ECL 2026/N.º74 de 18/02/2026' → 'ECL/2026/74'
            """
            if not desc:
                return None
            m = _re.search(r'ECL\s+(\d{4})/(N\.?[oº]?\.?\s*)?(\d+)', desc, _re.IGNORECASE)
            if m:
                return f"ECL/{m.group(1)}/{m.group(3)}"
            return None

        def _fp_from_descricao(desc):
            """Extrai ref FP/AAAA/NN da linha de texto (Folha de Picking intermédia)."""
            if not desc:
                return None
            m = _re.search(r'\bFP\s+(\d{4})/(N\.?[oº]?\.?\s*)?(\d+)', desc, _re.IGNORECASE)
            if m:
                return f"FP/{m.group(1)}/{m.group(3)}"
            return None

        def _ecl_from_fp(fp_ref):
            """Dada uma FP/AAAA/NN, busca a FP no Primavera e procura a ECL origem nela."""
            if not fp_ref:
                return None
            try:
                _, serie, num = fp_ref.split('/')
            except ValueError:
                return None
            filial = self.api_filial or "000"
            fp_data = self._edita(f"/v2/Vendas/Docs/Edita/{filial}/FP/{serie}/{num}")
            if not fp_data:
                return None
            # 1. Cabeçalho da FP
            ref = _ref(fp_data.get("TipoDocOrigem"), fp_data.get("SerieOrigem"), fp_data.get("NumDocOrigem"))
            if ref and ref.upper().startswith("ECL"):
                return ref
            # 2. Linhas da FP
            for fl in (fp_data.get("Linhas") or []):
                ref = _ref(fl.get("TipoDocOrigem"), fl.get("SerieOrigem"), fl.get("NumDocOrigem"))
                if ref and ref.upper().startswith("ECL"):
                    return ref
                if str(fl.get("TipoLinha", "")) == "60":
                    found = _ecl_from_descricao(self._clean(fl.get("Descricao")))
                    if found:
                        return found
            return None

        # Cabeçalho — campo direto
        ref = _ref(data.get("TipoDocOrigem"), data.get("SerieOrigem"), data.get("NumDocOrigem"))
        if ref and ref not in origens:
            origens.append(ref)

        # Cabeçalho — campos alternativos
        doc_origem_raw = self._clean(data.get("DocOrigem"))
        if doc_origem_raw and doc_origem_raw not in origens:
            origens.append(doc_origem_raw)

        # Linhas — acumular origens únicas
        for linha in (linhas or []):
            ref = _ref(linha.get("TipoDocOrigem"), linha.get("SerieOrigem"), linha.get("NumDocOrigem"))
            if ref and ref not in origens:
                origens.append(ref)

            # Linhas TipoLinha=60 (texto): Primavera gera "ECL 2026/N.º74 de ..." ou "FP 2026/N.º283 de ..."
            if str(linha.get("TipoLinha", "")) == "60":
                desc = self._clean(linha.get("Descricao"))
                ecl_ref = _ecl_from_descricao(desc)
                if ecl_ref and ecl_ref not in origens:
                    origens.append(ecl_ref)
                else:
                    # Fallback: linha FP — chama a API para descobrir a ECL origem da FP
                    fp_ref = _fp_from_descricao(desc)
                    if fp_ref:
                        ecl_via_fp = _ecl_from_fp(fp_ref)
                        if ecl_via_fp and ecl_via_fp not in origens:
                            origens.append(ecl_via_fp)

        # Último recurso: usar a tabela LinhasDocTrans do SQL Server (rastreabilidade real)
        # Faz BFS desde as linhas da fatura recuando IdLinhasDocOrigem→...→ECL
        if not any(o.upper().startswith("ECL/") for o in origens):
            tipo_fa = self._clean(data.get("TipoDoc")) or self._clean(data.get("Tipodoc"))
            serie_fa = self._clean(data.get("Serie"))
            num_fa = data.get("NumDoc")
            if tipo_fa and serie_fa and num_fa:
                ecl_via_sql = self._trace_ecl_via_sql(tipo_fa, serie_fa, num_fa)
                for ecl_ref in ecl_via_sql:
                    if ecl_ref not in origens:
                        origens.append(ecl_ref)

            # CamposUtil da linha
            for cu in linha.get("CamposUtil", []):
                nome = cu.get("Nome", "")
                val = self._clean(cu.get("Valor"))
                if nome in ("CDU_ECL", "CDU_DocOrigem", "CDU_RefOrigem") and val and val not in origens:
                    origens.append(val)

        return origens

    def _link_fatura_to_ecl(self, move, fatura_name, origens):
        """Liga a fatura a TODAS as ECLs encontradas nas origens.
        Quando uma fatura consolida várias ECLs (via GR), regista em todas."""
        if "sale.order" not in self.env:
            return
        SO = self.env["sale.order"].sudo()
        primeira_ecl = None
        for origem in origens:
            if not origem or not origem.upper().startswith("ECL"):
                continue
            ecl_so = SO.search([("primavera_ecl_ref", "=", origem)], limit=1)
            if not ecl_so:
                continue

            # ecl_sale_order_id em account.move só guarda 1 — usar a primeira
            if primeira_ecl is None:
                move.write({"ecl_sale_order_id": ecl_so.id})
                primeira_ecl = ecl_so

            # Adicionar ref da fatura à ECL (em TODAS as ECLs origem)
            existing_refs = ecl_so.primavera_fatura_refs or ""
            if fatura_name not in existing_refs:
                new_refs = f"{existing_refs}, {fatura_name}".strip(", ") if existing_refs else fatura_name
                ecl_so.write({"primavera_fatura_refs": new_refs})

            # Criar tasks "completar processo" em todas as ECLs origem
            self._criar_todos_ecl(ecl_so, fatura_name)

    def _get_or_create_tag_exportacao(self):
        """Obtém ou cria a tag 'Processo de Exportação' para tasks."""
        Tags = self.env['project.tags'].sudo()
        tag = Tags.search([('name', '=', 'Processo de Exportação')], limit=1)
        if not tag:
            tag = Tags.create({'name': 'Processo de Exportação', 'color': 2})
        return tag

    def _criar_todos_ecl(self, ecl_so, fatura_name):
        """Cria 1 task no To Do por responsável quando a FA é ligada à ECL."""
        if "project.task" not in self.env:
            return
        if not ecl_so.ecl_doc_line_ids:
            return

        Task    = self.env["project.task"].sudo()
        ecl_ref = ecl_so.primavera_ecl_ref or ecl_so.name
        cliente = ecl_so.partner_id.name or ''
        tag     = self._get_or_create_tag_exportacao()

        # Nome da task: "Completar processo ECL/AAAA/NN - Nome do Cliente"
        task_name = f"Completar processo {ecl_ref} - {cliente}"

        # Agrupar documentos pendentes por responsável
        user_docs = {}
        for line in ecl_so.ecl_doc_line_ids:
            doc_name = line.doc_type_id.name or "?"
            for user in line.responsible_ids:
                user_docs.setdefault(user.id, {"user": user, "docs": []})
                user_docs[user.id]["docs"].append(doc_name)

        for uid, info in user_docs.items():
            user     = info["user"]
            docs_str = ", ".join(info["docs"])

            # Evitar duplicado: mesmo título + mesmo utilizador
            if Task.search([("name", "=", task_name), ("user_ids", "in", [user.id])], limit=1):
                continue

            Task.create({
                "name": task_name,
                "description": (
                    f"<p>A fatura <strong>{fatura_name}</strong> foi emitida para a encomenda "
                    f"<strong>{ecl_ref}</strong> — <strong>{cliente}</strong>.</p>"
                    f"<p>Documentos a tratar: <strong>{docs_str}</strong></p>"
                ),
                "user_ids": [(4, user.id)],
                "tag_ids":  [(4, tag.id)],
                "project_id": False,
            })

    _MODO_TRANSPORTE = {
        "1": "Mar", "01": "Mar",
        "2": "Ferrovia", "02": "Ferrovia",
        "3": "Rodoviário", "03": "Rodoviário",
        "4": "Aéreo", "04": "Aéreo",
        "5": "Envios Postais", "05": "Envios Postais",
        "6": "Instalações Fixas", "06": "Instalações Fixas",
        "7": "Navegação Interior", "07": "Navegação Interior",
        "8": "Outro", "08": "Outro",
        "9": "Propulsão Própria", "09": "Propulsão Própria",
    }

    def _modo_transporte_desc(self, code):
        if not code:
            return False
        code_str = str(code).strip()
        return self._MODO_TRANSPORTE.get(code_str, code_str) or False

    def _clean(self, value):
        if value is None:
            return False
        if isinstance(value, str):
            return value.strip() or False
        return value

    def _join_lines(self, *values):
        lines = [self._clean(v) for v in values]
        return "\n".join(l for l in lines if l) or False

    def _format_vat(self, value, country_code):
        vat = self._clean(value)
        if not vat:
            return False
        vat = str(vat).replace(" ", "").replace("-", "")
        country = (self._clean(country_code) or "").upper()
        if len(country) == 2 and not vat.upper().startswith(country):
            return f"{country}{vat}"
        return vat

    def _country_id(self, country_code):
        code = self._clean(country_code)
        if not code:
            return False
        country = self.env["res.country"].sudo().search(
            [("code", "=", code.upper())], limit=1
        )
        return country.id or False

    def _barcode_available(self, barcode, current_product):
        domain = [("barcode", "=", barcode)]
        if current_product:
            domain.append(("id", "!=", current_product.id))
        return not self.env["product.template"].sudo().with_context(active_test=False).search_count(domain)

    def _parse_date(self, value):
        if not value:
            return False
        if isinstance(value, str):
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                try:
                    return datetime.strptime(value[:19], fmt).date()
                except ValueError:
                    continue
        return False

    def _stats_msg(self, stats):
        return _("Criados: %(created)s. Atualizados: %(updated)s. Ignorados: %(skipped)s.") % stats

    def _notify(self, title, message, msg_type="success"):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "type": msg_type,
                "sticky": False,
            },
        }

    def _log(self, operation, state, message):
        self.env["primavera.sync.log"].create({
            "connection_id": self.id,
            "operation": operation,
            "state": state,
            "message": message,
        })

    # ─────────────────────────────────────────────────────────────────────
    # VALIDAÇÃO MENSAL DE COMPOSIÇÕES
    # ─────────────────────────────────────────────────────────────────────

    _VALIDACAO_COMP_DESTINATARIOS = [
        "goncalo.simoes@mirazeite.com",
        "ricardo.nunes@mirazeite.com",
    ]
    _VALIDACAO_COMP_TOLERANCIA = 0.005  # 0,5%
    # Famílias de composto que são produto acabado engarrafado com granel F09
    _VALIDACAO_COMP_FAMILIAS_PRODUTO = ("F02", "F10", "F15")

    @staticmethod
    def _litros_da_descricao(desc):
        if not desc:
            return None
        d = desc.replace(",", ".").upper()
        m = re.search(r"(\d+)\s*[xX×]\s*([\d.]+)\s*ML\b", d)
        if m:
            return int(m.group(1)) * float(m.group(2)) / 1000.0
        m = re.search(r"(\d+)\s*[xX×]\s*([\d.]+)\s*L\b", d)
        if m:
            return int(m.group(1)) * float(m.group(2))
        m = re.search(r"\b([\d.]+)\s*ML\b", d)
        if m:
            return float(m.group(1)) / 1000.0
        m = re.search(r"\b([\d.]+)\s*L\b", d)
        if m:
            return float(m.group(1))
        return None

    def _validar_composicoes_mes(self, ano, mes):
        """Valida COMs do mês indicado. Devolve dict com resumo e lista de diferenças."""
        ini = date(ano, mes, 1)
        resultado = self._validar_composicoes_periodo(ini, ini + relativedelta(months=1))
        if resultado:
            resultado.update({"ano": ano, "mes": mes})
        return resultado

    def _validar_composicoes_periodo(self, ini, fim):
        """Valida COMs com Data em [ini, fim[. Devolve dict com resumo e lista de diferenças."""
        self.ensure_one()
        sql = self._sql_connection()
        if not sql:
            return None
        try:
            cur = sql.cursor(as_dict=True)
            cur.execute("""
                SELECT c.NumDoc, c.Serie, c.Data, c.Utilizador,
                       l.TipoComposto, l.Artigo, a.Descricao, a.Familia,
                       l.Quantidade
                FROM dbo.INV_CabecComposicoes c
                LEFT JOIN dbo.INV_LinhasComposicoes l ON l.IdCabecComposicoes = c.Id
                LEFT JOIN dbo.Artigo a ON a.Artigo = l.Artigo
                WHERE c.Data >= %s AND c.Data < %s AND c.TipoDoc = 'COM'
                ORDER BY c.Serie, c.NumDoc, l.TipoComposto DESC, l.NumLinha
            """, (ini.strftime("%Y-%m-%d"), fim.strftime("%Y-%m-%d")))
            rows = cur.fetchall()
        finally:
            try:
                sql.close()
            except Exception:
                pass

        docs = defaultdict(lambda: {
            "compostos": [], "azeite": 0.0, "mp_compostos_qtd": 0.0,
            "data": None, "user": None,
        })
        for r in rows:
            if not r["Artigo"]:
                continue
            d = docs[(r["NumDoc"], r["Serie"])]
            d["data"] = r["Data"]
            d["user"] = r["Utilizador"]
            if r["TipoComposto"] == 1:
                d["compostos"].append({
                    "desc": r["Descricao"],
                    "qtd": float(r["Quantidade"] or 0),
                    "litros_un": self._litros_da_descricao(r["Descricao"]),
                    "familia": r["Familia"],
                })
                if r["Familia"] == "F09":
                    d["mp_compostos_qtd"] += float(r["Quantidade"] or 0)
            elif r["Familia"] == "F09":
                d["azeite"] += float(r["Quantidade"] or 0)

        tol = self._VALIDACAO_COMP_TOLERANCIA
        n_ok = n_nao_aplica = 0
        diffs = []
        mp_falta = []
        for (num, serie), d in docs.items():
            parseaveis = [c for c in d["compostos"]
                          if c["litros_un"] and c["familia"] in self._VALIDACAO_COMP_FAMILIAS_PRODUTO]
            if not parseaveis:
                n_nao_aplica += 1
                continue
            esp = sum(c["qtd"] * c["litros_un"] for c in parseaveis)
            real = d["azeite"] - d["mp_compostos_qtd"]
            if esp == 0:
                n_nao_aplica += 1; continue
            if real <= 0:
                mp_falta.append({
                    "num": num, "serie": serie, "data": d["data"],
                    "composto": (d["compostos"][0]["desc"] or "")[:60],
                    "esp": esp, "user": d["user"],
                })
                continue
            perc = abs(real - esp) / esp
            if perc <= tol:
                n_ok += 1
            else:
                diffs.append({
                    "num": num, "serie": serie, "data": d["data"],
                    "composto": (d["compostos"][0]["desc"] or "")[:60],
                    "esp": esp, "real": real,
                    "delta": real - esp, "perc": perc * 100,
                })

        diffs.sort(key=lambda x: -x["perc"])
        mp_falta.sort(key=lambda x: -x["esp"])
        return {
            "ini": ini, "fim": fim,
            "total": len(docs),
            "ok": n_ok,
            "com_diferenca": len(diffs),
            "mp_em_falta": len(mp_falta),
            "nao_aplica": n_nao_aplica,
            "diffs": diffs,
            "mp_falta": mp_falta,
        }

    @staticmethod
    def _periodo_validacao_label(resultado):
        """'Setembro 2026' para resultados mensais; '19/09 a 25/09/2026' para semanais."""
        if resultado.get("mes"):
            meses_pt = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
            return f"{meses_pt[resultado['mes']]} {resultado['ano']}"
        ultimo = resultado["fim"] - timedelta(days=1)
        return f"{resultado['ini'].strftime('%d/%m')} a {ultimo.strftime('%d/%m/%Y')}"

    def _enviar_email_validacao(self, resultado, destinatarios=None):
        periodo = self._periodo_validacao_label(resultado)
        subject = f"Validação Composições — {periodo}"

        linhas_html = ""
        if resultado["diffs"]:
            for d in resultado["diffs"]:
                linhas_html += (
                    f"<tr><td>{d['num']}/{d.get('serie','')}</td>"
                    f"<td>{d['data'].strftime('%Y-%m-%d') if d['data'] else ''}</td>"
                    f"<td>{d['composto']}</td>"
                    f"<td style='text-align:right'>{d['esp']:,.2f}</td>"
                    f"<td style='text-align:right'>{d['real']:,.2f}</td>"
                    f"<td style='text-align:right'>{d['delta']:+,.2f}</td>"
                    f"<td style='text-align:right'>{d['perc']:.2f}%</td></tr>"
                )
            tabela = (
                "<h3>COMs com diferença</h3>"
                "<table border='1' cellpadding='4' cellspacing='0' "
                "style='border-collapse:collapse;font-family:monospace;font-size:12px'>"
                "<tr style='background:#eee'><th>NumDoc/Série</th><th>Data</th><th>Composto</th>"
                "<th>Esperado (L)</th><th>Real (L)</th><th>Delta</th><th>%</th></tr>"
                f"{linhas_html}</table>"
            )
        else:
            tabela = "<h3 style='color:green'>✓ Sem diferenças neste período</h3>"

        tabela_falta = ""
        if resultado.get("mp_falta"):
            linhas_f = ""
            for d in resultado["mp_falta"]:
                linhas_f += (
                    f"<tr><td>{d['num']}/{d.get('serie','')}</td>"
                    f"<td>{d['data'].strftime('%Y-%m-%d') if d['data'] else ''}</td>"
                    f"<td>{d['composto']}</td>"
                    f"<td style='text-align:right'>{d['esp']:,.2f}</td>"
                    f"<td>{d.get('user','')}</td></tr>"
                )
            tabela_falta = (
                "<h3 style='color:#b00'>COMs com MP em falta (sem consumo de azeite F09)</h3>"
                "<table border='1' cellpadding='4' cellspacing='0' "
                "style='border-collapse:collapse;font-family:monospace;font-size:12px'>"
                "<tr style='background:#eee'><th>NumDoc/Série</th><th>Data</th><th>Composto</th>"
                "<th>Esperado (L)</th><th>Utilizador</th></tr>"
                f"{linhas_f}</table>"
            )

        body = f"""
        <p>Validação automática das composições (COM) do Primavera.</p>
        <h3>Resumo — {periodo}</h3>
        <ul>
          <li><b>Total COMs analisados:</b> {resultado['total']}</li>
          <li><b>OK (delta ≤ 0,5%):</b> {resultado['ok']}</li>
          <li><b>Com diferença:</b> {resultado['com_diferenca']}</li>
          <li><b style='color:#b00'>MP em falta (esperado &gt; 0, sem MP F09 registada):</b> {resultado.get('mp_em_falta', 0)}</li>
          <li>Composto MP / sem litros na descrição: {resultado['nao_aplica']}</li>
        </ul>
        {tabela}
        {tabela_falta}
        <p style='color:#888;font-size:11px'>
          Critério: para cada composto da família F02/F15, litros esperados derivam
          da descrição (ex: "40x0,2L" → 8 L). Soma comparada com o total de MP da
          família F09 do mesmo COM, descontando compostos-MP. Tolerância 0,5%.
        </p>
        """
        self.env["mail.mail"].sudo().create({
            "subject": subject,
            "email_from": (self.env.user.email_formatted
                           or self.env.company.email
                           or "noreply@mirazeite.com"),
            "email_to": ",".join(destinatarios or self._VALIDACAO_COMP_DESTINATARIOS),
            "body_html": body,
        }).send()

    @api.model
    def _cron_validar_composicoes_mes_anterior(self):
        """Valida COMs do mês anterior e envia email.
        Agendado mensalmente (dia 3) via cron; também pode ser invocado em 'Run manually'."""
        today = fields.Date.context_today(self)
        anterior = today - relativedelta(months=1)
        conn = self.search([("active", "=", True)], limit=1)
        if not conn:
            return
        resultado = conn._validar_composicoes_mes(anterior.year, anterior.month)
        if not resultado:
            conn._log("validacao_composicoes", "error",
                      "Falha na ligação SQL ao Primavera.")
            return
        conn._enviar_email_validacao(resultado)
        conn._log(
            "validacao_composicoes", "success",
            f"{anterior.year}-{anterior.month:02d}: "
            f"total={resultado['total']} ok={resultado['ok']} "
            f"diff={resultado['com_diferenca']}",
        )

    # Validação semanal (sábado): só para o Gonçalo; o email mensal mantém-se.
    _VALIDACAO_SEMANAL_DESTINATARIOS = ["goncalo.simoes@mirazeite.com"]

    @api.model
    def _semana_anterior(self):
        """[sábado anterior, hoje[ — corrido ao sábado, cobre sábado a sexta."""
        fim = fields.Date.context_today(self)
        return fim - timedelta(days=7), fim

    @api.model
    def _cron_validar_composicoes_semana_anterior(self):
        """Valida COMs dos 7 dias anteriores e envia email.
        Agendado ao sábado via cron; também pode ser invocado em 'Run manually'."""
        ini, fim = self._semana_anterior()
        conn = self.search([("active", "=", True)], limit=1)
        if not conn:
            return
        resultado = conn._validar_composicoes_periodo(ini, fim)
        if not resultado:
            conn._log("validacao_composicoes", "error",
                      "Falha na ligação SQL ao Primavera.")
            return
        conn._enviar_email_validacao(resultado, self._VALIDACAO_SEMANAL_DESTINATARIOS)
        conn._log(
            "validacao_composicoes", "success",
            f"semana {conn._periodo_validacao_label(resultado)}: "
            f"total={resultado['total']} ok={resultado['ok']} "
            f"diff={resultado['com_diferenca']}",
        )

    # ─────────────────────────────────────────────────────────────────────
    # VALIDAÇÃO MENSAL DA PRODUÇÃO DO PREPARADO GRASO (MP.19)
    # ─────────────────────────────────────────────────────────────────────

    _VALIDACAO_PG_COMPOSTO     = "MP.19"
    _VALIDACAO_PG_COMPONENTES  = ("MP.10", "MP.36")
    _VALIDACAO_PG_TOLERANCIA   = 0.005  # 0,5%
    _VALIDACAO_PG_DESTINATARIO = "goncalo.simoes@mirazeite.com"

    def _validar_producao_prep_graso_mes(self, ano, mes):
        """Valida COMs do mês em que MP.19 é o composto (TipoComposto=1).
        Compara MP.19 líquido produzido com a soma dos componentes MP.10+MP.36.
        COMs que consomem outras MPs além destas são reportados como 'mistos'."""
        ini = date(ano, mes, 1)
        resultado = self._validar_producao_prep_graso_periodo(ini, ini + relativedelta(months=1))
        if resultado:
            resultado.update({"ano": ano, "mes": mes})
        return resultado

    def _validar_producao_prep_graso_periodo(self, ini, fim):
        """Como _validar_producao_prep_graso_mes, para COMs com Data em [ini, fim[."""
        self.ensure_one()
        composto = self._VALIDACAO_PG_COMPOSTO
        comps = set(self._VALIDACAO_PG_COMPONENTES)
        sql = self._sql_connection()
        if not sql:
            return None
        try:
            cur = sql.cursor(as_dict=True)
            cur.execute("""
                SELECT c.NumDoc, c.Serie, c.Data, c.Utilizador,
                       l.TipoComposto, l.Artigo, l.Quantidade
                FROM dbo.INV_CabecComposicoes c
                INNER JOIN dbo.INV_LinhasComposicoes l ON l.IdCabecComposicoes = c.Id
                WHERE c.TipoDoc='COM'
                  AND c.Data >= %s AND c.Data < %s
                  AND c.Id IN (
                      SELECT DISTINCT c2.Id
                      FROM dbo.INV_CabecComposicoes c2
                      INNER JOIN dbo.INV_LinhasComposicoes l2 ON l2.IdCabecComposicoes = c2.Id
                      WHERE c2.TipoDoc='COM'
                        AND c2.Data >= %s AND c2.Data < %s
                        AND l2.TipoComposto=1 AND l2.Artigo=%s
                  )
                ORDER BY c.Data, c.NumDoc, l.TipoComposto DESC
            """, (ini.strftime("%Y-%m-%d"), fim.strftime("%Y-%m-%d"),
                  ini.strftime("%Y-%m-%d"), fim.strftime("%Y-%m-%d"), composto))
            rows = cur.fetchall()
        finally:
            try: sql.close()
            except Exception: pass

        docs = defaultdict(lambda: {
            "data": None, "user": None,
            "produzido": 0.0, "recirc": 0.0,
            "componentes": {c: 0.0 for c in comps},
            "outros": defaultdict(float),
        })
        for r in rows:
            k = (r["NumDoc"], r["Serie"])
            d = docs[k]
            d["data"] = r["Data"]; d["user"] = r["Utilizador"]
            q = float(r["Quantidade"] or 0)
            art = r["Artigo"]
            if not art:
                continue
            if r["TipoComposto"] == 1:
                if art == composto:
                    d["produzido"] += q
            else:
                if art == composto:
                    d["recirc"] += q
                elif art in comps:
                    d["componentes"][art] += q
                else:
                    d["outros"][art] += q

        tol = self._VALIDACAO_PG_TOLERANCIA
        diffs = []
        mistos_list = []
        n_ok = 0
        tot_mp19 = tot_soma = 0.0
        tot_por_comp = {c: 0.0 for c in comps}
        ratios = {c: [] for c in comps}
        for (num, serie), d in docs.items():
            mp19 = d["produzido"] - d["recirc"]
            soma = sum(d["componentes"].values())
            delta = mp19 - soma
            perc = abs(delta) / mp19 * 100 if mp19 else 0.0
            base = {
                "num": num, "serie": serie, "data": d["data"], "user": d["user"],
                "mp19": mp19, "soma": soma, "delta": delta, "perc": perc,
            }
            base.update({c: d["componentes"][c] for c in comps})
            tot_mp19 += mp19
            tot_soma += soma
            for c in comps:
                tot_por_comp[c] += d["componentes"][c]
            if d["outros"]:
                outros_str = ", ".join(f"{a}={q:,.2f}" for a, q in sorted(d["outros"].items(), key=lambda x: -x[1]))
                mistos_list.append({**base, "outros": outros_str})
                continue
            if soma > 0:
                for c in comps:
                    ratios[c].append(d["componentes"][c] / soma * 100)
            if perc <= tol * 100:
                n_ok += 1
            else:
                diffs.append(base)

        diffs.sort(key=lambda x: -abs(x["delta"]))
        mistos_list.sort(key=lambda x: x["data"] or ini)

        def _mmm(lst):
            if not lst: return (0.0, 0.0, 0.0)
            return (sum(lst) / len(lst), min(lst), max(lst))
        ratios_stats = {c: _mmm(ratios[c]) for c in comps}
        delta_global = tot_mp19 - tot_soma
        perc_global = (delta_global / tot_mp19 * 100) if tot_mp19 else 0.0

        return {
            "ini": ini, "fim": fim,
            "total": len(docs),
            "ok": n_ok,
            "com_diferenca": len(diffs),
            "mistos": len(mistos_list),
            "diffs": diffs,
            "mistos_list": mistos_list,
            "totais": {
                "mp19": tot_mp19,
                "componentes": tot_por_comp,
                "soma": tot_soma,
                "delta": delta_global,
                "perc": perc_global,
            },
            "ratios": ratios_stats,
        }

    def _enviar_email_prep_graso(self, resultado):
        periodo = self._periodo_validacao_label(resultado)
        subject = f"Validação de Composições do Preparado Graso MP.19 — {periodo}"
        comps = list(self._VALIDACAO_PG_COMPONENTES)

        # Tabela de diferenças
        if resultado["diffs"]:
            linhas = ""
            for d in resultado["diffs"]:
                data = d["data"].strftime("%Y-%m-%d") if d["data"] else ""
                cols_comp = "".join(
                    f"<td style='text-align:right'>{d[c]:,.2f}</td>" for c in comps
                )
                linhas += (
                    f"<tr><td>{d['num']}/{d['serie']}</td>"
                    f"<td>{data}</td>"
                    f"<td style='text-align:right'>{d['mp19']:,.2f}</td>"
                    f"{cols_comp}"
                    f"<td style='text-align:right'>{d['soma']:,.2f}</td>"
                    f"<td style='text-align:right'>{d['delta']:+,.2f}</td>"
                    f"<td style='text-align:right'>{d['perc']:.2f}%</td>"
                    f"<td>{d['user'] or ''}</td></tr>"
                )
            hdr_comp = "".join(f"<th>{c} (L)</th>" for c in comps)
            tab_diff = (
                "<h3>COMs com diferença (fora tolerância 0,5%)</h3>"
                "<table border='1' cellpadding='4' cellspacing='0' "
                "style='border-collapse:collapse;font-family:monospace;font-size:12px'>"
                "<tr style='background:#eee'><th>NumDoc/Série</th><th>Data</th>"
                "<th>MP.19 líq. (L)</th>" + hdr_comp +
                "<th>Σ (L)</th><th>Δ</th><th>%</th><th>Utilizador</th></tr>"
                + linhas + "</table>"
            )
        else:
            tab_diff = "<h3 style='color:green'>✓ Sem diferenças acima da tolerância</h3>"

        # Tabela de mistos
        tab_mistos = ""
        if resultado["mistos_list"]:
            linhas = ""
            for d in resultado["mistos_list"]:
                data = d["data"].strftime("%Y-%m-%d") if d["data"] else ""
                cols_comp = "".join(
                    f"<td style='text-align:right'>{d[c]:,.2f}</td>" for c in comps
                )
                linhas += (
                    f"<tr><td>{d['num']}/{d['serie']}</td>"
                    f"<td>{data}</td>"
                    f"<td style='text-align:right'>{d['mp19']:,.2f}</td>"
                    f"{cols_comp}"
                    f"<td style='font-size:11px'>{d['outros']}</td>"
                    f"<td>{d['user'] or ''}</td></tr>"
                )
            hdr_comp = "".join(f"<th>{c} (L)</th>" for c in comps)
            tab_mistos = (
                "<h3 style='color:#a06000'>COMs mistos (com componentes fora de MP.10/MP.36)</h3>"
                "<p style='color:#666;font-size:11px'>Informacional — nestes COMs a lógica simples "
                "de balanço não se aplica porque há outras MPs em jogo (ou o próprio MP.19 é "
                "consumido no mesmo COM). Confirmar apenas se algum caso não faz sentido operacional.</p>"
                "<table border='1' cellpadding='4' cellspacing='0' "
                "style='border-collapse:collapse;font-family:monospace;font-size:12px'>"
                "<tr style='background:#eee'><th>NumDoc/Série</th><th>Data</th>"
                "<th>MP.19 líq. (L)</th>" + hdr_comp +
                "<th>Outros componentes</th><th>Utilizador</th></tr>"
                + linhas + "</table>"
            )

        # Ratios
        rat = resultado["ratios"]
        ratios_html = "<h3>Receita média (COMs balanceados)</h3><ul>"
        for c in comps:
            media, mn, mx = rat[c]
            ratios_html += f"<li><b>{c}:</b> média {media:.2f}% (min {mn:.2f}%, max {mx:.2f}%)</li>"
        ratios_html += "</ul>"

        # Totais globais
        tot = resultado["totais"]
        tot_comp_html = "".join(
            f"<li>{c} consumido: {tot['componentes'][c]:,.2f} L</li>" for c in comps
        )
        totais_html = (
            f"<h3>Totais globais — {periodo}</h3>"
            f"<ul>"
            f"<li>MP.19 líquido produzido: <b>{tot['mp19']:,.2f} L</b></li>"
            f"{tot_comp_html}"
            f"<li>Σ componentes: {tot['soma']:,.2f} L</li>"
            f"<li>Δ global: <b>{tot['delta']:+,.2f} L ({tot['perc']:+.3f}%)</b></li>"
            f"</ul>"
        )

        body = f"""
        <p>Validação automática mensal da produção do Preparado Graso (MP.19) —
        balanço entre MP.19 produzido e componentes {' + '.join(comps)}.</p>
        <h3>Resumo — {periodo}</h3>
        <ul>
          <li><b>Total COMs de MP.19:</b> {resultado['total']}</li>
          <li><b>OK (Δ ≤ 0,5%):</b> {resultado['ok']}</li>
          <li><b>Com diferença:</b> {resultado['com_diferenca']}</li>
          <li>Mistos (outras MPs presentes): {resultado['mistos']}</li>
        </ul>
        {tab_diff}
        {tab_mistos}
        {ratios_html}
        {totais_html}
        <p style='color:#888;font-size:11px'>
          Fonte: dbo.INV_CabecComposicoes + dbo.INV_LinhasComposicoes (TipoDoc='COM').
          Cada COM é agrupado por (NumDoc, Série). MP.19 líquido = produzido − MP.19
          reciclado no mesmo COM. Tolerância 0,5%.
        </p>
        """

        self.env["mail.mail"].sudo().create({
            "subject": subject,
            "email_from": (self.env.user.email_formatted
                           or self.env.company.email
                           or "noreply@mirazeite.com"),
            "email_to": self._VALIDACAO_PG_DESTINATARIO,
            "body_html": body,
        }).send()

    @api.model
    def _cron_validar_prep_graso_mes_anterior(self):
        """Valida a produção de MP.19 do mês anterior e envia email.
        Agendado mensalmente (dia 1) via cron; também pode ser invocado em 'Run manually'."""
        today = fields.Date.context_today(self)
        anterior = today - relativedelta(months=1)
        conn = self.search([("active", "=", True)], limit=1)
        if not conn:
            return
        resultado = conn._validar_producao_prep_graso_mes(anterior.year, anterior.month)
        if not resultado:
            conn._log("validacao_prep_graso", "error",
                      "Falha na ligação SQL ao Primavera.")
            return
        conn._enviar_email_prep_graso(resultado)
        conn._log(
            "validacao_prep_graso", "success",
            f"{anterior.year}-{anterior.month:02d}: "
            f"total={resultado['total']} ok={resultado['ok']} "
            f"diff={resultado['com_diferenca']} mistos={resultado['mistos']}",
        )

    @api.model
    def _cron_validar_prep_graso_semana_anterior(self):
        """Valida a produção de MP.19 dos 7 dias anteriores e envia email.
        Agendado ao sábado via cron; também pode ser invocado em 'Run manually'."""
        ini, fim = self._semana_anterior()
        conn = self.search([("active", "=", True)], limit=1)
        if not conn:
            return
        resultado = conn._validar_producao_prep_graso_periodo(ini, fim)
        if not resultado:
            conn._log("validacao_prep_graso", "error",
                      "Falha na ligação SQL ao Primavera.")
            return
        conn._enviar_email_prep_graso(resultado)
        conn._log(
            "validacao_prep_graso", "success",
            f"semana {conn._periodo_validacao_label(resultado)}: "
            f"total={resultado['total']} ok={resultado['ok']} "
            f"diff={resultado['com_diferenca']} mistos={resultado['mistos']}",
        )

    # ─────────────────────────────────────────────────────────────────────
    # REPORT AD-HOC: ECLs alterados hoje (activo apenas 2026-07-21 e 22)
    # ─────────────────────────────────────────────────────────────────────

    _ECL_REPORT_DESTINATARIO = "goncalo.simoes@mirazeite.com"
    _ECL_REPORT_ULTIMO_DIA = date(2026, 7, 22)

    @api.model
    def _cron_report_ecls_alterados_hoje(self):
        """Envia por email todas as ECLs alteradas hoje no Primavera.
        Auto-desactiva-se após 2026-07-22."""
        today = fields.Date.context_today(self)
        conn = self.search([("active", "=", True)], limit=1)
        if not conn:
            return

        conn._enviar_report_ecls_alterados_hoje()

        # Auto-desactivar após o último dia
        if today >= self._ECL_REPORT_ULTIMO_DIA:
            cron = self.env.ref(
                "primavera_connector.ir_cron_primavera_report_ecls_hoje",
                raise_if_not_found=False,
            )
            if cron:
                cron.sudo().active = False

    def _enviar_report_ecls_alterados_hoje(self):
        """Recolhe ECLs actualizadas hoje e envia email HTML."""
        self.ensure_one()
        today = fields.Date.context_today(self)
        today_start = datetime.combine(today, datetime.min.time())
        today_end = today_start + timedelta(days=1)

        sql = self._sql_connection()
        if not sql:
            self._log("report_ecls", "error", "Sem ligação SQL ao Primavera.")
            return
        try:
            cur = sql.cursor(as_dict=True)
            cur.execute("""
                SELECT c.Id, c.NumDoc, c.Serie, c.Data, c.DataUltimaActualizacao,
                       c.Utilizador, c.Entidade, c.Nome
                FROM dbo.CabecDoc c
                WHERE c.TipoDoc = 'ECL'
                  AND c.DataUltimaActualizacao >= %s AND c.DataUltimaActualizacao < %s
                ORDER BY c.DataUltimaActualizacao DESC
            """, (today_start, today_end))
            ecls = cur.fetchall()

            linhas_por_ecl = {}
            for e in ecls:
                cur.execute("""
                    SELECT NumLinha, Artigo, Descricao, Quantidade, Unidade,
                           PrecUnit, Desconto1, PrecoLiquido
                    FROM dbo.LinhasDoc
                    WHERE IdCabecDoc = %s
                    ORDER BY NumLinha
                """, (e["Id"],))
                linhas_por_ecl[e["Id"]] = cur.fetchall()
        finally:
            try:
                sql.close()
            except Exception:
                pass

        subject = f"Report ECLs alteradas hoje ({today.strftime('%Y-%m-%d')}) — {len(ecls)}"

        if not ecls:
            body = f"<p>Nenhuma ECL foi alterada hoje ({today}).</p>"
        else:
            tabelas = []
            for e in ecls:
                cab = (
                    f"<h3 style='margin-top:20px'>ECL {e['Serie']}/{e['NumDoc']} — "
                    f"{e['Nome'] or ''}</h3>"
                    f"<p style='margin:0;color:#666'>Actualizado: "
                    f"{e['DataUltimaActualizacao']} &nbsp;|&nbsp; "
                    f"Utilizador: {e['Utilizador'] or '?'} &nbsp;|&nbsp; "
                    f"Cliente: {e['Entidade']}</p>"
                )
                linhas_html = ""
                for l in linhas_por_ecl.get(e["Id"], []):
                    linhas_html += (
                        f"<tr>"
                        f"<td>{l['NumLinha']}</td>"
                        f"<td>{l['Artigo'] or ''}</td>"
                        f"<td>{(l['Descricao'] or '')[:50]}</td>"
                        f"<td style='text-align:right'>{l['Quantidade']:.2f}</td>"
                        f"<td>{l['Unidade'] or ''}</td>"
                        f"<td style='text-align:right'>{l['PrecUnit']:.4f}</td>"
                        f"<td style='text-align:right'>{l['Desconto1'] or 0:.2f}%</td>"
                        f"<td style='text-align:right'>{l['PrecoLiquido']:.2f}</td>"
                        f"</tr>"
                    )
                tabela = (
                    f"{cab}"
                    "<table border='1' cellpadding='4' cellspacing='0' "
                    "style='border-collapse:collapse;font-family:monospace;font-size:11px'>"
                    "<tr style='background:#eee'>"
                    "<th>L</th><th>Artigo</th><th>Descrição</th>"
                    "<th>Qtd</th><th>Un</th><th>Preço Un</th>"
                    "<th>Desc</th><th>Líquido</th></tr>"
                    f"{linhas_html}</table>"
                )
                tabelas.append(tabela)
            body = (
                f"<p>{len(ecls)} ECL(s) actualizada(s) hoje no Primavera. "
                f"Detalhe abaixo:</p>{''.join(tabelas)}"
                "<p style='color:#888;font-size:11px;margin-top:20px'>"
                "Nota: o Primavera não guarda historial de preços — este report mostra "
                "o estado <b>actual</b> dos preços das linhas."
                "</p>"
            )

        self.env["mail.mail"].sudo().create({
            "subject": subject,
            "email_from": (self.env.user.email_formatted
                           or self.env.company.email
                           or "noreply@mirazeite.com"),
            "email_to": self._ECL_REPORT_DESTINATARIO,
            "body_html": body,
        }).send()

        self._log("report_ecls", "success",
                  f"{today}: {len(ecls)} ECLs enviadas para {self._ECL_REPORT_DESTINATARIO}")

    # ─────────────────────────────────────────────────────────────────────
    # REPORT MENSAL: FAs para Brasil no mês
    # ─────────────────────────────────────────────────────────────────────

    _FA_BR_REPORT_DESTINATARIO = "goncalo.simoes@mirazeite.com"

    _MESES_PT = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                 "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

    def _get_docs_brasil(self, date_ini, date_fim, tipos):
        """Devolve documentos (dicts) para Brasil no período [date_ini, date_fim).
        `tipos` é uma lista de TipoDoc (ex: ['FA'] ou ['NC','NCAA','NCAT','NCT','NCDT']).
        Filtro de país: campo custom CDU_Pais = 'BR' (definido pelo utilizador na ficha)."""
        self.ensure_one()
        sql = self._sql_connection()
        if not sql:
            return None
        ph = ",".join(["%s"] * len(tipos))
        try:
            cur = sql.cursor(as_dict=True)
            cur.execute(f"""
                SELECT c.TipoDoc, c.NumDoc, c.Serie, c.Data, c.Nome, c.Entidade,
                       c.CDU_Pais, c.TotalMerc
                FROM dbo.CabecDoc c
                JOIN dbo.CabecDocStatus s ON s.IdCabecDoc = c.Id
                WHERE c.TipoDoc IN ({ph})
                  AND c.Data >= %s AND c.Data < %s
                  AND ISNULL(s.Anulado,0) = 0
                  AND LTRIM(RTRIM(c.CDU_Pais)) = 'BR'
                ORDER BY c.Data, c.TipoDoc, c.NumDoc
            """, tuple(tipos) + (date_ini.strftime("%Y-%m-%d"),
                                 date_fim.strftime("%Y-%m-%d")))
            return cur.fetchall()
        finally:
            try:
                sql.close()
            except Exception:
                pass

    def _get_fas_brasil(self, date_ini, date_fim):
        """Wrapper legado — apenas FAs."""
        return self._get_docs_brasil(date_ini, date_fim, ['FA'])

    _NC_TIPOS = ['NC', 'NCAA', 'NCAT', 'NCT', 'NCDT']

    def _seccoes_docs_html(self, rows, label_singular, label_plural):
        """Devolve HTML com tabelas Por mês / Por cliente / Detalhe para o conjunto `rows`.
        Retorna string vazia se não há linhas — o chamador pode substituir por mensagem."""
        if not rows:
            return ""
        from collections import defaultdict
        por_mes = defaultdict(lambda: {"n": 0, "total": 0.0})
        por_cli = defaultdict(lambda: {"n": 0, "total": 0.0, "docs": []})
        for r in rows:
            m = r["Data"].strftime("%Y-%m")
            por_mes[m]["n"] += 1
            por_mes[m]["total"] += float(r["TotalMerc"] or 0)
            nome = r["Nome"] or "?"
            por_cli[nome]["n"] += 1
            por_cli[nome]["total"] += float(r["TotalMerc"] or 0)
            por_cli[nome]["docs"].append(f"{r['TipoDoc']}/{r['Serie']}/{r['NumDoc']}")

        html_mes = "".join(
            f"<tr><td>{m}</td><td style='text-align:right'>{d['n']}</td>"
            f"<td style='text-align:right'>{d['total']:,.2f}</td></tr>"
            for m, d in sorted(por_mes.items())
        )
        html_cli = "".join(
            f"<tr><td style='text-align:right'>{v['n']}</td>"
            f"<td style='text-align:right'>{v['total']:,.2f}</td>"
            f"<td>{k}</td><td style='font-size:10px;color:#666'>{', '.join(v['docs'])}</td></tr>"
            for k, v in sorted(por_cli.items(), key=lambda x: -x[1]["n"])
        )
        html_det = "".join(
            f"<tr><td>{r['TipoDoc']}/{r['Serie']}/{r['NumDoc']}</td>"
            f"<td>{r['Data'].strftime('%Y-%m-%d')}</td>"
            f"<td style='text-align:right'>{float(r['TotalMerc']):,.2f}</td>"
            f"<td>{(r['Nome'] or '')[:50]}</td></tr>"
            for r in rows
        )
        return f"""
            <h4>Por mês</h4>
            <table border='1' cellpadding='4' cellspacing='0'
                   style='border-collapse:collapse;font-family:monospace;font-size:12px'>
              <tr style='background:#eee'><th>Mês</th><th># {label_plural}</th><th>Total €</th></tr>
              {html_mes}
            </table>

            <h4>Por cliente</h4>
            <table border='1' cellpadding='4' cellspacing='0'
                   style='border-collapse:collapse;font-family:monospace;font-size:12px'>
              <tr style='background:#eee'><th># {label_plural}</th><th>Total €</th>
                  <th>Cliente</th><th>Documentos</th></tr>
              {html_cli}
            </table>

            <h4>Detalhe cronológico</h4>
            <table border='1' cellpadding='4' cellspacing='0'
                   style='border-collapse:collapse;font-family:monospace;font-size:11px'>
              <tr style='background:#eee'><th>Doc</th><th>Data</th><th>Total €</th><th>Cliente</th></tr>
              {html_det}
            </table>
        """

    def _enviar_email_fa_br(self, ano, mes_ini, mes_fim, titulo_periodo,
                            destinatario=None, incluir_ytd=False):
        """Envia email com FAs e NCs destino Brasil no intervalo [mes_ini, mes_fim].
        Filtro país: CDU_Pais='BR' (campo utilizador na ficha do documento).
        incluir_ytd: se True, acrescenta secção final com totais YTD (FAs + NCs)."""
        self.ensure_one()
        date_ini = date(ano, mes_ini, 1)
        date_fim = date(ano + (1 if mes_fim == 12 else 0),
                        1 if mes_fim == 12 else mes_fim + 1, 1)

        fas = self._get_docs_brasil(date_ini, date_fim, ['FA']) or []
        ncs = self._get_docs_brasil(date_ini, date_fim, self._NC_TIPOS) or []

        destinatario = destinatario or self._FA_BR_REPORT_DESTINATARIO
        total_fas = sum(float(r["TotalMerc"] or 0) for r in fas)
        total_ncs = sum(float(r["TotalMerc"] or 0) for r in ncs)
        subject = (f"Docs destino Brasil — {titulo_periodo} "
                   f"({len(fas)} FAs · {total_fas:,.2f} € | "
                   f"{len(ncs)} NCs · {total_ncs:,.2f} €)")

        # ─── Secção FATURAS ───
        if fas:
            sec_fa = (f"<h2>Faturas (FA) — {titulo_periodo}</h2>"
                      f"<p><b>Total: {len(fas)} FAs · {total_fas:,.2f} €</b></p>"
                      + self._seccoes_docs_html(fas, "FA", "FAs"))
        else:
            sec_fa = (f"<h2>Faturas (FA) — {titulo_periodo}</h2>"
                      f"<p>Sem FAs destino Brasil no período.</p>")

        # ─── Secção NOTAS DE CRÉDITO ───
        if ncs:
            sec_nc = (f"<h2 style='margin-top:30px'>Notas de Crédito (NC) — "
                      f"{titulo_periodo}</h2>"
                      f"<p><b>Total: {len(ncs)} NCs · {total_ncs:,.2f} €</b><br>"
                      f"<small>Tipos considerados: {', '.join(self._NC_TIPOS)}</small></p>"
                      + self._seccoes_docs_html(ncs, "NC", "NCs"))
        else:
            sec_nc = (f"<h2 style='margin-top:30px'>Notas de Crédito (NC) — "
                      f"{titulo_periodo}</h2>"
                      f"<p>Sem Notas de Crédito destino Brasil no período.</p>")

        body = sec_fa + sec_nc

        # ─── YTD do ano corrente ───
        if incluir_ytd:
            hoje = fields.Date.context_today(self)
            ytd_ini = date(hoje.year, 1, 1)
            ytd_fim = hoje + timedelta(days=1)
            ytd_fas = self._get_docs_brasil(ytd_ini, ytd_fim, ['FA']) or []
            ytd_ncs = self._get_docs_brasil(ytd_ini, ytd_fim, self._NC_TIPOS) or []
            ytd_total_fa = sum(float(r["TotalMerc"] or 0) for r in ytd_fas)
            ytd_total_nc = sum(float(r["TotalMerc"] or 0) for r in ytd_ncs)
            body += (
                f"<h3 style='margin-top:30px'>YTD {hoje.year} — acumulado até hoje "
                f"({hoje.strftime('%Y-%m-%d')})</h3>"
                f"<ul style='font-size:14px'>"
                f"<li><b>Faturas:</b> {len(ytd_fas)} FAs — {ytd_total_fa:,.2f} €</li>"
                f"<li><b>Notas de Crédito:</b> {len(ytd_ncs)} NCs — {ytd_total_nc:,.2f} €</li>"
                f"<li><b>Líquido (FAs − NCs):</b> "
                f"{ytd_total_fa - ytd_total_nc:,.2f} €</li>"
                f"</ul>"
            )

        self.env["mail.mail"].sudo().create({
            "subject": subject,
            "email_from": (self.env.user.email_formatted
                           or self.env.company.email
                           or "noreply@mirazeite.com"),
            "email_to": destinatario,
            "body_html": body,
        }).send()

        self._log("report_fa_br", "success",
                  f"{titulo_periodo}: {len(fas)} FAs ({total_fas:,.2f} €) + "
                  f"{len(ncs)} NCs ({total_ncs:,.2f} €) → {destinatario}")

    # ─────────────────────────────────────────────────────────────────────
    # ALERTA GR/GRT por faturar (sextas + último dia do mês)
    # ─────────────────────────────────────────────────────────────────────

    _GR_GRT_ALERTA_ASSIGNEES = (
        "goncalo.simoes@mirazeite.com",
        "carmo.cordeiro@mirazeite.com",
        "claudia.zacarias@mirazeite.com",
    )
    _GR_GRT_TASK_PREFIX = "[Primavera] GR/GRT por faturar"

    @staticmethod
    def _parse_ecl_ref(text):
        """Extrai (ano, num) do texto 'ECL YYYY/N.º NN de DD/MM/YYYY'."""
        if not text:
            return None, None
        m = re.search(r"ECL\s+(\d{4})/N\.?[oºº]?\.?\s*(\d+)", text, re.IGNORECASE)
        return (m.group(1), m.group(2)) if m else (None, None)

    _GR_GRT_ANO_MINIMO = 2026  # ignorar anos anteriores (erros iniciais de setup)

    def _get_gr_grt_por_faturar(self):
        """Devolve GR e GRT realmente por faturar.
        Regras:
        - Ano >= _GR_GRT_ANO_MINIMO
        - Estado='P', não anuladas, não fechadas
        - Filtra fora as que já foram transformadas em FA ou FAT
          (via tabela de rastreabilidade dbo.LinhasDocTrans)
        """
        self.ensure_one()
        sql = self._sql_connection()
        if not sql:
            return None
        try:
            cur = sql.cursor(as_dict=True)
            cur.execute("""
                SELECT c.TipoDoc, c.NumDoc, c.Serie, c.Data, c.Nome, c.Entidade,
                       c.TotalMerc, c.Utilizador,
                       DATEDIFF(day, c.Data, GETDATE()) AS DiasAberto
                FROM dbo.CabecDoc c
                JOIN dbo.CabecDocStatus s ON s.IdCabecDoc = c.Id
                WHERE c.TipoDoc IN ('GR','GRT')
                  AND ISNULL(s.Anulado,0) = 0
                  AND ISNULL(s.Fechado,0) = 0
                  AND s.Estado = 'P'
                  AND YEAR(c.Data) >= %s
                  AND NOT EXISTS (
                      SELECT 1
                      FROM dbo.LinhasDoc l_orig
                      JOIN dbo.LinhasDocTrans t ON t.IdLinhasDocOrigem = l_orig.Id
                      JOIN dbo.LinhasDoc l_dest ON l_dest.Id = t.IdLinhasDoc
                      JOIN dbo.CabecDoc c_dest ON c_dest.Id = l_dest.IdCabecDoc
                      JOIN dbo.CabecDocStatus s_dest ON s_dest.IdCabecDoc = c_dest.Id
                      WHERE l_orig.IdCabecDoc = c.Id
                        AND c_dest.TipoDoc IN ('FA','FAT')
                        AND ISNULL(s_dest.Anulado,0) = 0
                  )
                ORDER BY c.Data, c.TipoDoc, c.NumDoc
            """, (self._GR_GRT_ANO_MINIMO,))
            return cur.fetchall()
        finally:
            try:
                sql.close()
            except Exception:
                pass

    def _render_gr_grt_html(self, rows):
        """Devolve HTML com tabela de GR/GRT + resumo."""
        n_gr = sum(1 for r in rows if r["TipoDoc"] == "GR")
        n_grt = sum(1 for r in rows if r["TipoDoc"] == "GRT")
        total = sum(float(r["TotalMerc"] or 0) for r in rows)
        linhas = "".join(
            f"<tr>"
            f"<td>{r['TipoDoc']}</td>"
            f"<td>{r['Serie']}/{r['NumDoc']}</td>"
            f"<td>{r['Data'].strftime('%Y-%m-%d')}</td>"
            f"<td style='text-align:right'>{r['DiasAberto']}</td>"
            f"<td>{r['Entidade']}</td>"
            f"<td>{(r['Nome'] or '')[:50]}</td>"
            f"<td style='text-align:right'>{float(r['TotalMerc'] or 0):,.2f}</td>"
            f"<td>{r['Utilizador'] or ''}</td>"
            f"</tr>"
            for r in rows
        )
        return f"""
            <p><b>{len(rows)} documentos</b> em aberto:
               {n_gr} GR + {n_grt} GRT — Total <b>{total:,.2f} €</b></p>
            <table border='1' cellpadding='4' cellspacing='0'
                   style='border-collapse:collapse;font-family:monospace;font-size:11px'>
              <tr style='background:#eee'>
                <th>Tipo</th><th>Nº Doc</th><th>Data</th><th>Dias abertos</th>
                <th>Cód. Cli</th><th>Cliente</th>
                <th>Total €</th><th>Utilizador</th>
              </tr>
              {linhas}
            </table>
            <p style='color:#888;font-size:11px;margin-top:10px'>
              Critério: GR/GRT com Estado='P' (Pendente), não anuladas, não fechadas.
              Ano ≥ {self._GR_GRT_ANO_MINIMO}. Não foram convertidas em FA (GR → A1 Arruda)
              nem em FAT (GRT → A2 Tomar).
            </p>
        """

    def _criar_ou_atualizar_task_gr_grt(self, rows):
        """Cria uma task privada (sem projecto) com os 3 assignees, ou actualiza
        se já existir uma task aberta com o mesmo prefixo."""
        self.ensure_one()
        n_gr = sum(1 for r in rows if r["TipoDoc"] == "GR")
        n_grt = sum(1 for r in rows if r["TipoDoc"] == "GRT")
        titulo = (f"{self._GR_GRT_TASK_PREFIX} — {len(rows)} docs "
                  f"({n_gr} GR + {n_grt} GRT)")
        html = self._render_gr_grt_html(rows)

        # Resolver users a partir dos emails/logins
        Users = self.env["res.users"].sudo()
        assignees = Users.search([
            ("login", "in", [e.lower() for e in self._GR_GRT_ALERTA_ASSIGNEES])
        ])
        if not assignees:
            self._log("alerta_gr_grt", "error",
                      f"Nenhum utilizador encontrado com logins "
                      f"{self._GR_GRT_ALERTA_ASSIGNEES}")
            return

        Task = self.env["project.task"].sudo()
        # Procurar task aberta existente do prefixo, sem projecto, ainda não fechada
        existente = Task.search([
            ("name", "=like", f"{self._GR_GRT_TASK_PREFIX}%"),
            ("project_id", "=", False),
            ("state", "not in", ["1_done", "1_canceled"]),
        ], limit=1)

        hoje = fields.Date.context_today(self)
        if existente:
            existente.write({
                "name": titulo,
                "description": html,
                "user_ids": [(6, 0, assignees.ids)],
            })
            existente.message_post(
                body=(f"<p><b>Atualização {hoje}</b>: {len(rows)} GR/GRT "
                      f"ainda por faturar.</p>{html}"),
                subject=titulo,
            )
            self._log("alerta_gr_grt", "success",
                      f"Task #{existente.id} atualizada: {len(rows)} docs")
            return existente
        else:
            task = Task.create({
                "name": titulo,
                "description": html,
                "user_ids": [(6, 0, assignees.ids)],
                "project_id": False,  # task privada
            })
            self._log("alerta_gr_grt", "success",
                      f"Task #{task.id} criada: {len(rows)} docs")
            return task

    @api.model
    def _cron_alerta_gr_grt_por_faturar(self):
        """Corre diariamente às 07:00 UTC (08h Lisboa). Só executa se hoje for
        Sexta OU último dia do mês. Só envia email se houver GR/GRT em aberto."""
        today = fields.Date.context_today(self)
        is_sexta = today.weekday() == 4  # 0=segunda, 4=sexta
        is_ultimo_dia = (today + timedelta(days=1)).month != today.month
        if not (is_sexta or is_ultimo_dia):
            return
        conn = self.search([("active", "=", True)], limit=1)
        if not conn:
            return
        rows = conn._get_gr_grt_por_faturar()
        if rows is None:
            conn._log("alerta_gr_grt", "error", "Sem ligação SQL ao Primavera.")
            return
        if not rows:
            return  # nada em aberto → não cria/actualiza task
        conn._criar_ou_atualizar_task_gr_grt(rows)

    @api.model
    def _cron_report_fa_br_mensal(self):
        """Corre diariamente. Se hoje for o último dia do mês, envia o report do mês corrente."""
        today = fields.Date.context_today(self)
        amanha = today + timedelta(days=1)
        if amanha.month == today.month:
            return  # ainda não é último dia
        conn = self.search([("active", "=", True)], limit=1)
        if not conn:
            return
        titulo = f"{self._MESES_PT[today.month]} {today.year}"
        conn._enviar_email_fa_br(
            today.year, today.month, today.month, titulo, incluir_ytd=True,
        )
