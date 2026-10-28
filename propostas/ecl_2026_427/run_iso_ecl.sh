#!/bin/bash
# odoo shell na BD de teste isolada com os ficheiros da proposta (ecl_mounts.txt) por cima. Uso: run_iso6d.sh <db> <script> [antigo]
T=/home/odoo/.claude/jobs/738b98e4/tmp
EXTRA=()
if [ "$3" != "antigo" ]; then for m in $(cat $T/ecl_mounts.txt); do EXTRA+=(-v "$m:ro"); done; fi
exec docker run --rm -i --network odoo_test_net --entrypoint odoo \
  -v "$T/test_odoo.conf:/etc/odoo/test.conf:ro" -v "$T/out:/out" \
  -v /home/odoo/odoo/extra-addons:/mnt/extra-addons:ro "${EXTRA[@]}" \
  -v /home/odoo/odoo/muk-addons:/mnt/muk-addons:ro -v /home/odoo/odoo/oca-web:/mnt/oca-web:ro -v odoo_odoo_data:/var/lib/odoo:ro \
  odoo18-primavera:18.0 shell -c /etc/odoo/test.conf -d "$1" --no-http --max-cron-threads=0 < "$2"
