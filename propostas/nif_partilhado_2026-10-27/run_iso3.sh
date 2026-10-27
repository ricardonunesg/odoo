#!/bin/bash
# odoo shell em BD de teste isolada, com o conector E o NIF Dedup do worktree por cima. Uso: run_iso3.sh <db> <script>
T=/home/odoo/.claude/jobs/738b98e4/tmp
WT=/home/odoo/odoo/.claude/worktrees/primavera-incremental-sync/extra-addons
exec docker run --rm -i --network odoo_test_net --entrypoint odoo \
  -v "$T/test_odoo.conf:/etc/odoo/test.conf:ro" -v "$T/out:/out" \
  -v /home/odoo/odoo/extra-addons:/mnt/extra-addons:ro \
  -v "$WT/primavera_connector/models/primavera_connection.py:/mnt/extra-addons/primavera_connector/models/primavera_connection.py:ro" \
  -v "$WT/mirazeite_partner_nif_dedup/models/res_partner.py:/mnt/extra-addons/mirazeite_partner_nif_dedup/models/res_partner.py:ro" \
  -v /home/odoo/odoo/muk-addons:/mnt/muk-addons:ro -v /home/odoo/odoo/oca-web:/mnt/oca-web:ro -v odoo_odoo_data:/var/lib/odoo:ro \
  odoo18-primavera:18.0 shell -c /etc/odoo/test.conf -d "$1" --no-http --max-cron-threads=0 < "$2"
