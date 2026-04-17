from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class PrimaveraConnection(models.Model):
    _name = "primavera.connection"
    _description = "Ligacao Primavera"
    _rec_name = "name"

    name = fields.Char(default="Primavera SQL01", required=True)
    active = fields.Boolean(default=True)
    server = fields.Char(default="SQL01", required=True)
    instance = fields.Char(default="PRIMAVERA")
    port = fields.Integer(
        default=0,
        help="Use 0 para instancias SQL Server nomeadas. Preencha apenas quando souber a porta TCP fixa.",
    )
    database = fields.Char(required=True)
    username = fields.Char(required=True)
    password = fields.Char(required=True, copy=False)
    sync_customers = fields.Boolean(default=True)
    sync_suppliers = fields.Boolean(default=True)
    sync_products = fields.Boolean(default=True)
    tds_version = fields.Selection(
        [
            ("7.2", "7.2"),
            ("7.3", "7.3"),
            ("7.4", "7.4"),
        ],
        default="7.4",
        required=True,
    )
    trust_server_certificate = fields.Boolean(default=True)
    last_connection_test = fields.Datetime(readonly=True)
    last_connection_message = fields.Text(readonly=True)
    last_sync_date = fields.Datetime(readonly=True)
    last_sync_message = fields.Text(readonly=True)

    def _get_pyodbc(self):
        try:
            import pyodbc
        except ImportError as exc:
            raise UserError(
                _(
                    "O Python package 'pyodbc' nao esta instalado no container Odoo. "
                    "Reconstrua o container com a imagem customizada deste projeto."
                )
            ) from exc
        return pyodbc

    def _connection_string(self):
        self.ensure_one()
        trust = "yes" if self.trust_server_certificate else "no"
        server = self.server
        if self.instance:
            server = "%s\\%s" % (server, self.instance)
        values = [
            "DRIVER={FreeTDS}",
            "SERVER=%s" % server,
            "DATABASE=%s" % self.database,
            "UID=%s" % self.username,
            "PWD=%s" % self.password,
            "TDS_Version=%s" % self.tds_version,
            "TrustServerCertificate=%s" % trust,
        ]
        if self.port:
            values.insert(2, "PORT=%s" % self.port)
        return ";".join(values) + ";"

    def _masked_connection_string(self):
        self.ensure_one()
        return (
            "DRIVER={FreeTDS};"
            "SERVER=%s;"
            "%s"
            "DATABASE=%s;"
            "UID=%s;"
            "PWD=***;"
            "TDS_Version=%s;"
            "TrustServerCertificate=%s;"
        ) % (
            "%s\\%s" % (self.server, self.instance) if self.instance else self.server,
            "PORT=%s;" % self.port if self.port else "",
            self.database,
            self.username,
            self.tds_version,
            "yes" if self.trust_server_certificate else "no",
        )

    def _connect(self, timeout=10):
        self.ensure_one()
        pyodbc = self._get_pyodbc()
        return pyodbc.connect(self._connection_string(), timeout=timeout)

    def action_test_connection(self):
        for connection in self:
            try:
                with connection._connect(timeout=10) as sql_connection:
                    cursor = sql_connection.cursor()
                    cursor.execute("SELECT DB_NAME(), @@SERVERNAME")
                    database_name, server_name = cursor.fetchone()
                message = _("Ligacao OK. Base de dados: %s. Servidor: %s.") % (
                    database_name,
                    server_name,
                )
                connection.write(
                    {
                        "last_connection_test": fields.Datetime.now(),
                        "last_connection_message": message,
                    }
                )
                connection._log("connection", "success", message)
            except Exception as exc:
                message = _("Falha na ligacao: %s") % exc
                connection.write(
                    {
                        "last_connection_test": fields.Datetime.now(),
                        "last_connection_message": message,
                    }
                )
                connection._log("connection", "error", message)
                raise UserError(message) from exc

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Primavera"),
                "message": _("Teste de ligacao concluido com sucesso."),
                "type": "success",
                "sticky": False,
            },
        }

    def action_import_customers(self):
        self.ensure_one()
        stats = self._import_partners("customer")
        return self._notification(_("Clientes importados"), self._stats_message(stats))

    def action_import_suppliers(self):
        self.ensure_one()
        stats = self._import_partners("supplier")
        return self._notification(_("Fornecedores importados"), self._stats_message(stats))

    def action_import_products(self):
        self.ensure_one()
        stats = {"created": 0, "updated": 0, "skipped": 0}
        Product = self.env["product.template"].sudo().with_context(active_test=False)

        with self._connect(timeout=30) as sql_connection:
            cursor = sql_connection.cursor()
            cursor.execute(
                """
                SELECT
                    Artigo, Descricao, CodBarras, UnidadeBase, UnidadeVenda,
                    Familia, TipoArtigo, ArtigoAnulado, Observacoes,
                    DataUltimaActualizacao
                FROM dbo.Artigo
                """
            )
            for row in cursor.fetchall():
                data = self._row_dict(cursor, row)
                code = self._clean(data.get("Artigo"))
                name = self._clean(data.get("Descricao"))
                if not code or not name:
                    stats["skipped"] += 1
                    continue

                product = Product.search([("primavera_code", "=", code)], limit=1)
                vals = {
                    "name": name,
                    "default_code": code,
                    "primavera_code": code,
                    "active": not bool(data.get("ArtigoAnulado")),
                    "sale_ok": True,
                    "purchase_ok": True,
                }
                barcode = self._clean(data.get("CodBarras"))
                if barcode and self._barcode_available(barcode, product):
                    vals["barcode"] = barcode
                elif barcode:
                    stats["skipped"] += 1

                observations = self._clean(data.get("Observacoes"))
                if observations:
                    vals["description"] = observations

                if product:
                    product.write(vals)
                    stats["updated"] += 1
                else:
                    Product.create(vals)
                    stats["created"] += 1

        message = self._stats_message(stats)
        self._log("products", "success", message)
        return self._notification(_("Artigos importados"), message)

    def action_sync_all(self):
        for connection in self:
            connection._sync_all()
        return self._notification(_("Primavera"), _("Sincronizacao concluida."))

    def _sync_all(self):
        self.ensure_one()
        messages = []
        try:
            if self.sync_customers:
                stats = self._import_partners("customer")
                messages.append(_("Clientes: %s") % self._stats_message(stats))
            if self.sync_suppliers:
                stats = self._import_partners("supplier")
                messages.append(_("Fornecedores: %s") % self._stats_message(stats))
            if self.sync_products:
                product_action = self.action_import_products()
                messages.append(_("Artigos: %s") % product_action["params"]["message"])

            message = "\n".join(messages) or _("Nada para sincronizar.")
            self.write(
                {
                    "last_sync_date": fields.Datetime.now(),
                    "last_sync_message": message,
                }
            )
            self._log("sync_all", "success", message)
            return message
        except Exception as exc:
            message = _("Falha na sincronizacao: %s") % exc
            self.write(
                {
                    "last_sync_date": fields.Datetime.now(),
                    "last_sync_message": message,
                }
            )
            self._log("sync_all", "error", message)
            raise

    @api.model
    def cron_sync_active_connections(self):
        for connection in self.search([("active", "=", True)]):
            connection._sync_all()

    def _import_partners(self, partner_type):
        self.ensure_one()
        if partner_type == "customer":
            query = """
                SELECT
                    Cliente AS Codigo, Nome, NomeFiscal, Fac_Mor AS Morada,
                    Fac_Mor1 AS Morada1, Fac_Mor2 AS Morada2, Fac_Local AS Localidade,
                    Fac_Cp AS CodigoPostal, Fac_Cploc AS LocalidadePostal,
                    Fac_Tel AS Telefone, Telefone2, Email, EnderecoWeb,
                    NumContrib, Pais, ClienteAnulado AS Anulado, Notas,
                    DataUltimaActualizacao
                FROM dbo.Clientes
            """
            code_field = "primavera_customer_code"
            rank_field = "customer_rank"
            operation = "customers"
            category_xmlid = "primavera_connector.partner_category_primavera_customer"
        else:
            query = """
                SELECT
                    Fornecedor AS Codigo, Nome, NomeFiscal, Morada,
                    Morada1, Morada2, Local AS Localidade,
                    Cp AS CodigoPostal, CpLoc AS LocalidadePostal,
                    Tel AS Telefone, NULL AS Telefone2, Email, EnderecoWeb,
                    NumContrib, Pais, FornecedorAnulado AS Anulado, Notas,
                    DataUltimaActualizacao
                FROM dbo.Fornecedores
            """
            code_field = "primavera_supplier_code"
            rank_field = "supplier_rank"
            operation = "suppliers"
            category_xmlid = "primavera_connector.partner_category_primavera_supplier"

        stats = {"created": 0, "updated": 0, "skipped": 0}
        Partner = self.env["res.partner"].sudo().with_context(active_test=False)
        category = self.env.ref(category_xmlid)
        with self._connect(timeout=30) as sql_connection:
            cursor = sql_connection.cursor()
            cursor.execute(query)
            for row in cursor.fetchall():
                data = self._row_dict(cursor, row)
                code = self._clean(data.get("Codigo"))
                name = self._clean(data.get("NomeFiscal")) or self._clean(data.get("Nome"))
                if not code or not name:
                    stats["skipped"] += 1
                    continue

                partner = Partner.search([(code_field, "=", code)], limit=1)
                vat = self._format_vat(data.get("NumContrib"), data.get("Pais"))
                if not partner and partner_type == "customer":
                    partner = self._find_existing_import_partner(vat)

                street = self._join_lines(data.get("Morada"), data.get("Morada1"))
                vals = {
                    "name": name,
                    "is_company": True,
                    "company_type": "company",
                    code_field: code,
                    rank_field: 1,
                    "street": street,
                    "street2": self._clean(data.get("Morada2")),
                    "city": self._clean(data.get("Localidade")) or self._clean(data.get("LocalidadePostal")),
                    "zip": self._clean(data.get("CodigoPostal")),
                    "phone": self._clean(data.get("Telefone")),
                    "mobile": self._clean(data.get("Telefone2")),
                    "email": self._clean(data.get("Email")),
                    "website": self._clean(data.get("EnderecoWeb")),
                    "vat": vat,
                    "country_id": self._country_id(data.get("Pais")),
                    "active": not bool(data.get("Anulado")),
                    "comment": self._clean(data.get("Notas")),
                    "category_id": [(4, category.id)],
                }
                vals = {key: value for key, value in vals.items() if value not in (None, "")}

                invalid_vat = False
                if partner:
                    invalid_vat = self._safe_write_partner(partner, vals)
                    stats["updated"] += 1
                else:
                    invalid_vat = self._safe_create_partner(Partner, vals)
                    stats["created"] += 1
                if invalid_vat:
                    stats["skipped"] += 1

        message = self._stats_message(stats)
        self._log(operation, "success", message)
        return stats

    def action_tag_existing_crm_contacts(self):
        self.ensure_one()
        category = self.env.ref("primavera_connector.partner_category_crm_prospect")
        leads = self.env["crm.lead"].sudo().search([("partner_id", "!=", False)])
        partners = leads.mapped("partner_id")
        partners.write({"category_id": [(4, category.id)]})
        message = _("Contactos CRM marcados: %s.") % len(partners)
        self._log("customers", "success", message)
        return self._notification(_("Contactos CRM"), message)

    def action_tag_odoo_user_contacts(self):
        self.ensure_one()
        category = self.env.ref("primavera_connector.partner_category_odoo_user")
        partners = self.env["res.users"].sudo().search([]).mapped("partner_id")
        partners.write({"category_id": [(4, category.id)]})
        message = _("Contactos de utilizadores Odoo marcados: %s.") % len(partners)
        self._log("customers", "success", message)
        return self._notification(_("Utilizadores Odoo"), message)

    def _find_existing_import_partner(self, vat):
        if not vat:
            return self.env["res.partner"]
        partners = self.env["res.partner"].sudo().with_context(active_test=False).search([("vat", "=", vat)])
        partners = partners.filtered(lambda partner: self._can_reuse_partner_for_import(partner))
        return partners if len(partners) == 1 else self.env["res.partner"]

    def _can_reuse_partner_for_import(self, partner):
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
            retry_vals = self._vals_without_invalid_vat(vals)
            with self.env.cr.savepoint():
                Partner.create(retry_vals)
            return True

    def _safe_write_partner(self, partner, vals):
        try:
            with self.env.cr.savepoint():
                partner.write(vals)
            return False
        except ValidationError:
            if not vals.get("vat"):
                raise
            retry_vals = self._vals_without_invalid_vat(vals)
            with self.env.cr.savepoint():
                partner.write(retry_vals)
            return True

    def _vals_without_invalid_vat(self, vals):
        retry_vals = dict(vals)
        invalid_vat = retry_vals.pop("vat", False)
        if invalid_vat:
            note = _("NIF/VAT Primavera nao importado por validacao Odoo: %s") % invalid_vat
            existing_comment = retry_vals.get("comment")
            retry_vals["comment"] = self._join_lines(existing_comment, note)
        return retry_vals

    def _row_dict(self, cursor, row):
        columns = [column[0] for column in cursor.description]
        return dict(zip(columns, row))

    def _clean(self, value):
        if value is None:
            return False
        if isinstance(value, str):
            return value.strip() or False
        return value

    def _join_lines(self, *values):
        lines = [self._clean(value) for value in values]
        return "\n".join(line for line in lines if line) or False

    def _format_vat(self, value, country_code):
        vat = self._clean(value)
        if not vat:
            return False
        vat = str(vat).replace(" ", "").replace("-", "")
        country = (self._clean(country_code) or "").upper()
        if len(country) == 2 and not vat.upper().startswith(country):
            return "%s%s" % (country, vat)
        return vat

    def _country_id(self, country_code):
        code = self._clean(country_code)
        if not code:
            return False
        country = self.env["res.country"].sudo().search([("code", "=", code.upper())], limit=1)
        return country.id or False

    def _barcode_available(self, barcode, current_product):
        domain = [("barcode", "=", barcode)]
        if current_product:
            domain.append(("id", "!=", current_product.id))
        return not self.env["product.template"].sudo().with_context(active_test=False).search_count(domain)

    def _stats_message(self, stats):
        return _("Criados: %(created)s. Atualizados: %(updated)s. Ignorados: %(skipped)s.") % stats

    def _notification(self, title, message):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "type": "success",
                "sticky": False,
            },
        }

    def _log(self, operation, state, message):
        self.env["primavera.sync.log"].create(
            {
                "connection_id": self.id,
                "operation": operation,
                "state": state,
                "message": message,
            }
        )
