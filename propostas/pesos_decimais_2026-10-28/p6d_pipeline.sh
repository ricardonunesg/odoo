#!/bin/bash
T=/home/odoo/.claude/jobs/738b98e4/tmp; set -o pipefail
MOUNTS=$(cat $T/p6d_mounts.txt)
F() { grep -E "^R |Traceback|Error:" | grep -v "ocmobileapp\|NameResolution\|MaxRetry\|ConnectionError" | cut -c1-500; }
docker exec odoo18_db pg_dump -U odoo -Fc mirazeite > $T/prod_p6d.dump || exit 1
docker network create --internal odoo_test_net >/dev/null
docker run -d --name odoo_test_pg --network odoo_test_net -e POSTGRES_USER=odoo -e POSTGRES_PASSWORD=testpw -e POSTGRES_DB=postgres --tmpfs /var/lib/postgresql/data:rw,size=8g postgres:15 >/dev/null
until docker exec odoo_test_pg pg_isready -U odoo >/dev/null 2>&1; do sleep 2; done
for db in u r; do docker exec odoo_test_pg createdb -U odoo $db && docker exec -i odoo_test_pg pg_restore -U odoo -d $db --no-owner --exit-on-error < $T/prod_p6d.dump; echo "restauro $db=$?"; docker exec odoo_test_pg psql -U odoo -d $db -At -c "update ir_mail_server set active=false; update fetchmail_server set active=false;" >/dev/null; done
{ echo "[options]"; echo "db_host = odoo_test_pg"; echo "db_port = 5432"; echo "db_user = odoo"; echo "db_password = testpw"; echo "list_db = False"; echo "data_dir = /tmp/odoo-test-data"; echo "workers = 0"; echo "max_cron_threads = 0"; echo "smtp_server = 127.0.0.1"; echo "smtp_port = 1"; grep -E '^\s*(addons_path|proxy_mode)' /home/odoo/odoo/config/odoo.conf; } > $T/test_odoo.conf
echo "rede bloqueada: $(docker run --rm --network odoo_test_net -v $T/netcheck.py:/tmp/netcheck.py:ro --entrypoint python3 odoo18-primavera:18.0 /tmp/netcheck.py | grep -c bloqueado)/6"
echo "===== 1. fotografia antes"; python3 $T/snapshot.py u $T/p6d_antes.txt; docker exec -i odoo_test_pg psql -U odoo -d u -At -F'|' < $T/p6_snap.sql > $T/p6d_pesos_antes.txt
echo "===== 2. -u primavera_connector com a proposta"; bash $T/run_upgrade.sh u $MOUNTS > $T/p6d_upgrade.log 2>&1; echo "saída=$?"
grep -E " (ERROR|CRITICAL) |Traceback" $T/p6d_upgrade.log | grep -v "certificado.health\|ocmobileapp\|NameResolution" | head -10; grep -c "Loading module\|module .* loading" $T/p6d_upgrade.log; grep -E "upgrading|Modules loaded|updating modules list" $T/p6d_upgrade.log | tail -3
echo "===== 3. fotografia depois e diferenças"; python3 $T/snapshot.py u $T/p6d_depois.txt; python3 $T/diffsnap.py $T/p6d_antes.txt $T/p6d_depois.txt 40
docker exec -i odoo_test_pg psql -U odoo -d u -At -F'|' < $T/p6_snap.sql > $T/p6d_pesos_depois.txt; echo "pesos/volumes de documentos e artigos alterados pela actualização: $(diff $T/p6d_pesos_antes.txt $T/p6d_pesos_depois.txt | grep -c '^>')"
echo "===== 4. ensaio funcional"; bash $T/run_iso6d.sh u $T/p6d_test.py 2>&1 | F
echo "===== 5. reversão: -u com o código actual de produção"; bash $T/run_upgrade.sh r $MOUNTS > $T/p6d_upgrade_r1.log 2>&1; echo "-u proposta saída=$?"; bash $T/run_upgrade.sh r > $T/p6d_upgrade_r2.log 2>&1; echo "-u reversão saída=$?"
grep -E " (ERROR|CRITICAL) |Traceback" $T/p6d_upgrade_r2.log | grep -v "certificado.health\|ocmobileapp\|NameResolution" | head -5
python3 $T/snapshot.py r $T/p6d_rev.txt; python3 $T/diffsnap.py $T/p6d_antes.txt $T/p6d_rev.txt 40
bash $T/run_iso6d.sh r $T/p6d_rev_check.py antigo 2>&1 | F
echo "===== FIM"
