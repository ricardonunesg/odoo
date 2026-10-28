#!/bin/bash
# -u primavera_connector numa BD de teste, em rede interna (sem saída), sem crons nem http.
# Uso: run_upgrade.sh <db> [origem:destino ...]  (ficheiros a montar por cima, só leitura)
T=/home/odoo/.claude/jobs/738b98e4/tmp
DB=$1; shift
EXTRA=()
for m in "$@"; do EXTRA+=(-v "$m:ro"); done
exec docker run --rm --network odoo_test_net --entrypoint odoo \
  -v "$T/test_odoo.conf:/etc/odoo/test.conf:ro" \
  -v /home/odoo/odoo/extra-addons:/mnt/extra-addons:ro \
  -v /home/odoo/odoo/muk-addons:/mnt/muk-addons:ro \
  -v /home/odoo/odoo/oca-web:/mnt/oca-web:ro \
  -v odoo_odoo_data:/var/lib/odoo:ro \
  "${EXTRA[@]}" \
  odoo18-primavera:18.0 -c /etc/odoo/test.conf -d "$DB" -u primavera_connector \
  --stop-after-init --no-http --max-cron-threads=0 --log-level=info
