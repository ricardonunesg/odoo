#!/bin/bash
# odoo shell na BD de teste isolada. Uso: run_iso6.sh <db> <script> [proposta]  (proposta = 4 ficheiros do documentos do worktree por cima)
EXTRA=()
if [ "$3" = "proposta" ]; then
  for f in sale_order_ext account_move_ext packing_list boletim_analises; do
    EXTRA+=(-v "/home/odoo/odoo/.claude/worktrees/primavera-incremental-sync/extra-addons/documentos/models/$f.py:/mnt/extra-addons/documentos/models/$f.py:ro")
  done
fi
exec docker run --rm -i --network odoo_test_net --entrypoint odoo \
  -v "/home/odoo/.claude/jobs/738b98e4/tmp/test_odoo.conf:/etc/odoo/test.conf:ro" -v "/home/odoo/.claude/jobs/738b98e4/tmp/out:/out" \
  -v /home/odoo/odoo/extra-addons:/mnt/extra-addons:ro "${EXTRA[@]}" \
  -v /home/odoo/odoo/muk-addons:/mnt/muk-addons:ro -v /home/odoo/odoo/oca-web:/mnt/oca-web:ro -v odoo_odoo_data:/var/lib/odoo:ro \
  odoo18-primavera:18.0 shell -c /etc/odoo/test.conf -d "$1" --no-http --max-cron-threads=0 < "$2"
