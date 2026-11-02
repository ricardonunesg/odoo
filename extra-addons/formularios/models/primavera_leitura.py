import re
from contextlib import contextmanager

from odoo import models, _
from odoo.exceptions import UserError

# Acesso ao Primavera SÓ DE LEITURA: qualquer instrução que não seja um SELECT é recusada antes de ser enviada.
_SO_LEITURA = re.compile(r'^\s*(SELECT|WITH)\b', re.I)
_ESCRITA = re.compile(r'\b(INSERT|UPDATE|DELETE|MERGE|DROP|ALTER|CREATE|TRUNCATE|EXEC|EXECUTE|GRANT|REVOKE|DENY|INTO|OPENROWSET|OPENQUERY)\b', re.I)


class _Leitor:
    def __init__(self, cursor):
        self._cursor = cursor

    def q(self, consulta, *params):
        if not _SO_LEITURA.match(consulta) or _ESCRITA.search(consulta):
            raise UserError(_("Consulta ao Primavera recusada: só são permitidas leituras (SELECT)."))
        self._cursor.execute(consulta, params or None)
        return self._cursor.fetchall()


class PrimaveraLeitura(models.AbstractModel):
    _name = 'formularios.primavera.leitura'
    _description = 'Leitura (só SELECT) da base de dados do Primavera'

    @contextmanager
    def _ligacao(self):
        """Ligação SQL ao Primavera (a configurada no Conector, limite de 5 s por consulta), fechada no fim.
        Uso: with env['formularios.primavera.leitura']._ligacao() as ler: ler.q("SELECT ...", p1, p2)"""
        ligacao = self.env['primavera.connection'].sudo().search([('active', '=', True)], limit=1)
        sql = ligacao._sql_connection() if ligacao else None
        if not sql:
            raise UserError(_("Sem ligação ao Primavera neste momento. Tente mais tarde."))
        try:
            yield _Leitor(sql.cursor())
        finally:
            sql.close()
