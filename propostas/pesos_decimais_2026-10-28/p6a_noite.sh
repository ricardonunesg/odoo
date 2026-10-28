#!/bin/bash
T=/home/odoo/.claude/jobs/738b98e4/tmp; C=/home/odoo/backups_config
Q() { docker exec odoo18_db psql -U odoo -d mirazeite -At -F' | ' -c "$1"; }
until [ "$(Q "select count(*) from primavera_sync_log where operation='ecls' and message like '[completo]%' and create_date >= '2026-10-29 01:30'")" -ge 1 ]; do sleep 120; done
sleep 120
echo "=== verificação A $(date)"
Q "select create_date::timestamp(0), left(message,100) from primavera_sync_log where operation='ecls' and message like '[completo]%' and create_date >= '2026-10-29 01:30'"
docker exec -i odoo18_app odoo shell -d mirazeite --no-http < $T/p6a_noite.py 2>&1 | grep -E '^R |Traceback'
docker exec -i odoo18_db psql -U odoo -d mirazeite -At -F'|' < $T/p6_snap.sql > $T/pesos_29.txt
echo "--- valores alterados desde a aplicação, por tipo (sol = linhas de ECL; o resto deve ser 0 salvo documentos novos):"
diff $C/pesos_snapshot.2026-10-28_pre-pesos.txt $T/pesos_29.txt | grep '^>' | cut -c3- | cut -d'|' -f1 | sort | uniq -c
echo "--- linhas de fatura/PL/boletim EXISTENTES alteradas (deve ser vazio):"
join -t'|' -j1 <(awk -F'|' '$1!="sol"{print $1":"$2"|"$0}' $C/pesos_snapshot.2026-10-28_pre-pesos.txt | sort) <(awk -F'|' '$1!="sol"{print $1":"$2"|"$0}' $T/pesos_29.txt | sort) | awk -F'|' '{n=(NF-1)/2; a=""; b=""; for(i=2;i<=n+1;i++)a=a"|"$i; for(i=n+2;i<=NF;i++)b=b"|"$i; if(a!=b)print $1}' | head -20
echo "erros no Odoo desde a aplicação: $(docker logs --since 2026-10-28T12:33:48 odoo18_app 2>&1 | grep -E ' (ERROR|CRITICAL) |Traceback' | grep -vc 'certificado.health')"
echo "=== fim"
