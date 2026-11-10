# Instruções permanentes — Mirazeite (servidor Odoo)

## REGRA OBRIGATÓRIA — instalar/atualizar módulos Odoo em produção (Gonçalo, 10/11/2026)

Checklist completo e oficial: `/home/odoo/git-mirazeite/ODOO/docs/PROCEDIMENTO_PRODUCAO.md`
(ler e seguir **antes** de qualquer instalação ou atualização em produção).

Nunca alterar produção sem autorização expressa do Gonçalo (cada alteração; autorizações anteriores não valem).
Quando uma instalação ou atualização envolve código Python, o procedimento inclui **obrigatoriamente**:

1. Backup prévio (`pg_dump` + SHA-256 + restauro validado) e reversão preparada (cópia da pasta da versão atual, ensaiada).
2. Atualização **apenas** dos módulos autorizados.
3. **Reinício controlado do serviço** (`docker restart odoo18_app`) depois do `-u`/`-i`, para os processos web
   carregarem o novo Python — o `-u` noutro processo não o faz.
4. Confirmar que o serviço voltou a responder e que os crons estão operacionais, sem execuções indevidas.
5. Confirmar que Python, JavaScript e XML carregados em produção são da mesma versão.
6. Testar a funcionalidade pelos **processos web reais** (browser), não só pelo `odoo shell`.
7. Verificar erros no servidor (`docker logs`) e no browser.

- **Nunca contornar a segurança** para validar no browser. Se não for possível, dizer ao Gonçalo que falta a
  validação dele (com a lista exata do que testar) e **não** declarar a atualização validada.
- **Nunca considerar uma atualização concluída só porque o `-u` terminou sem erros.**

Origem: incidente do Histórico Primavera 1.2.0 (10/11/2026) — `-u` sem reinício deixou Python 1.1.0 em memória
com JavaScript 1.2.0 → janela em erro (`reading 'year_cur'`).
