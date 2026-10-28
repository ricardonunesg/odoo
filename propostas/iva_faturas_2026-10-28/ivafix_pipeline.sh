#!/bin/bash
T=/home/odoo/.claude/jobs/738b98e4/tmp
docker exec odoo18_db pg_dump -U odoo -Fc mirazeite > $T/prod_ivafix.dump || exit 1
docker network create --internal odoo_test_net >/dev/null
docker run -d --name odoo_test_pg --network odoo_test_net -e POSTGRES_USER=odoo -e POSTGRES_PASSWORD=testpw -e POSTGRES_DB=postgres --tmpfs /var/lib/postgresql/data:rw,size=8g postgres:15 >/dev/null
until docker exec odoo_test_pg pg_isready -U odoo >/dev/null 2>&1; do sleep 2; done
docker exec odoo_test_pg createdb -U odoo fx && docker exec -i odoo_test_pg pg_restore -U odoo -d fx --no-owner --exit-on-error < $T/prod_ivafix.dump; echo "restauro=$?"
docker exec odoo_test_pg psql -U odoo -d fx -At -c "update ir_mail_server set active=false; update fetchmail_server set active=false;" >/dev/null
{ echo "[options]"; echo "db_host = odoo_test_pg"; echo "db_port = 5432"; echo "db_user = odoo"; echo "db_password = testpw"; echo "list_db = False"; echo "data_dir = /tmp/odoo-test-data"; echo "workers = 0"; echo "max_cron_threads = 0"; echo "smtp_server = 127.0.0.1"; echo "smtp_port = 1"; grep -E '^\s*(addons_path|proxy_mode)' /home/odoo/odoo/config/odoo.conf; } > $T/test_odoo.conf
echo "rede bloqueada: $(docker run --rm --network odoo_test_net -v $T/netcheck.py:/tmp/netcheck.py:ro --entrypoint python3 odoo18-primavera:18.0 /tmp/netcheck.py | grep -c bloqueado)/6"
for modo in ensaio-protegido; do
  echo "===== $modo"
  { echo "MODO = '$modo'"; cat $T/iva_fix.py; } > $T/iva_fix_run.py
  bash $T/run_iso6d.sh fx $T/iva_fix_run.py antigo 2>&1 | grep -E "^R |Traceback|Error:" | grep -v "ocmobileapp\|NameResolution\|MaxRetry\|ConnectionError" | cut -c1-900
done
docker rm -f odoo_test_pg >/dev/null; docker network rm odoo_test_net >/dev/null; rm -f $T/prod_ivafix.dump $T/test_odoo.conf $T/iva_fix_run.py
echo "===== FIM"
