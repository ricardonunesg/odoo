# Ponto 5: nova sincronização com os dados reais gravados da WebAPI (sem ligação ao Primavera).
# Reimporta as 88 faturas e re-sincroniza as 25 ECLs com desconto, e grava o resultado.
import json
from unittest import mock
from odoo.addons.primavera_connector.models import primavera_connection as M
dados = json.load(open("/out/p3_dados.json"))
api = dados["api"]
c = env["primavera.connection"].browse(1)

def fake_edita(self, ep, strict=False):
    parts = ep.rstrip("/").split("/")
    ref = "/".join(parts[-3:])
    return api.get(ref)

with mock.patch.object(M.PrimaveraConnection, "_edita", fake_edita), \
     mock.patch.object(M.PrimaveraConnection, "_sql_connection", return_value=None), \
     mock.patch.object(M.PrimaveraConnection, "_ecl_notify_partners", return_value=env["res.partner"]):
    n_fat = n_ecl = 0
    for ref in sorted(api):
        t, s, n = ref.split("/")
        if t == "ECL":
            if c._resync_single_ecl(ref):
                n_ecl += 1
        else:
            c._import_faturas_doc(t, s, int(n) - 1, 1, 1, None)
            n_fat += 1
env.cr.commit()
print("R nova sincronização: faturas reimportadas", n_fat, "| ECLs re-sincronizadas", n_ecl)
