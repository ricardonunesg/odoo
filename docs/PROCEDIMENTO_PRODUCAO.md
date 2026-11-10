# Procedimento obrigatório — instalação e atualização de módulos Odoo em produção

Regra permanente da Mirazeite (Gonçalo Simões, 10/11/2026). Aplica-se a **todas** as instalações (`-i`)
e atualizações (`-u`) de módulos no Odoo de produção (contentor `odoo18_app`, base `mirazeite`).

> Origem: no Histórico Primavera 1.2.0 (10/11/2026) o `-u` terminou sem erros, mas o serviço não foi
> reiniciado. Os processos web continuaram com o Python antigo em memória, enquanto o JavaScript/XML
> já eram os novos → a janela deixou de abrir (`Cannot read properties of undefined (reading 'year_cur')`).
> A validação feita só com `odoo shell` (processo novo) não detetou o problema.

## Princípios
- **Nada em produção sem autorização expressa do Gonçalo** — para cada alteração; autorizações anteriores não valem.
- **Uma atualização não está concluída só porque o `-u` terminou sem erros.**
- **Nunca contornar a segurança** (sessões, permissões, passwords) para validar. Se não for possível validar
  no browser, a atualização fica **"instalada — falta a validação do Gonçalo"**, nunca "validada".
- Atualizar **apenas** os módulos autorizados.

## Antes de produção (ensaio isolado)
- [ ] Desenvolvimento num *worktree*; ensaio numa cópia da base noutro Postgres temporário, rede Docker
      `--internal`, crons/servidores de email desligados na cópia, `docker rm -fv` no fim (ver disco com `df -h /`).
- [ ] Testes proporcionais ao risco, incluindo **o browser** no ensaio quando há JavaScript/XML.
- [ ] Ensaio do `-u` **e** da reversão (voltar à versão anterior) na cópia, com fotografia antes/depois.
- [ ] Indicar se a alteração tem **código Python** (instalação nova ou ficheiros `.py` alterados) → o reinício
      do serviço é obrigatório (passo 4).

## Em produção (depois da autorização)
1. **Backup e reversão**
   - [ ] `pg_dump -Fc` da base → `/home/odoo/backups/db_AAAA-MM-DD_pre-<assunto>.dump` + `.sha256`; restauro validado num Postgres isolado.
   - [ ] Cópia da pasta do módulo **tal como está em produção** → `/home/odoo/backups/modulo_<nome>_<versão>_<data>/`.
   - [ ] Plano de reversão escrito (repor a pasta guardada → `-u` do módulo → reinício), ensaiado na cópia.
2. **Fotografia antes**: crons (ativo, intervalo, próxima execução), módulos e versões, acessos, regras, grupos,
   numerações, menus, vistas, parâmetros, servidores de email/fetchmail, seguidores, mensagens.
3. **Instalação/atualização só dos módulos autorizados**
   - [ ] Copiar só a(s) pasta(s) autorizada(s) para `/home/odoo/odoo/extra-addons/` (sem `__pycache__`); `diff -r` com o worktree = igual.
   - [ ] `docker exec odoo18_app odoo -c /etc/odoo/odoo.conf -d mirazeite -u <módulo> --stop-after-init --no-http --max-cron-threads=0`
         (`-i` para módulo novo) — sem `ERROR`/`Traceback`.
4. **Reinício controlado do serviço** (obrigatório sempre que há código Python)
   - [ ] Antes: sem consultas longas em curso (`pg_stat_activity`) nem tarefas agendadas a meio.
   - [ ] `docker restart odoo18_app` e esperar que `http://127.0.0.1:8069/web/login` responda (dentro do contentor).
5. **Serviço e crons operacionais**
   - [ ] Processos Odoo arrancaram **depois** da cópia dos ficheiros (`ps -eo lstart,args` vs `stat` dos `.py`).
   - [ ] `WorkerCron … alive` no registo; nenhum cron ativo atrasado > 5 min; crons inativos continuam inativos
         (comparar com a fotografia) — sem execuções indevidas.
6. **Mesma versão em Python, JavaScript e XML**
   - [ ] `ir_module_module.latest_version` = versão do `__manifest__.py` no disco.
   - [ ] Pacote servido por HTTP (`/web/assets/_/web.assets_backend.min.js` e `.css`) contém o código novo,
         sem `Could not get content` nem erro de SCSS.
   - [ ] Python carregado pelos processos web = ficheiros no disco (prova: hora de arranque do passo 5).
7. **Teste pelos processos web reais** — não chega o `odoo shell`
   - [ ] Funcionalidade testada no **browser** em produção, com os dados reais (F5/Ctrl+F5 antes).
   - [ ] Se o Claude não puder entrar no browser sem contornar permissões: **parar**, entregar ao Gonçalo a
         lista exata do que testar e marcar "falta a validação do Gonçalo".
   - [ ] `odoo shell` (só leitura, `rollback`) apenas como complemento: dados, permissões, comparação com SQL.
8. **Erros no servidor e no browser**
   - [ ] `docker logs --since <instalação> odoo18_app` sem `ERROR`/`CRITICAL`/`Traceback` novos
         (erro antigo conhecido e ignorado: `Missing model certificado.health`).
   - [ ] Consola do browser sem erros (diálogo "Oops!"/`OwlError`).
9. **Fotografia depois** e comparação: só podem mudar o(s) módulo(s) autorizado(s) e a próxima execução de crons
   frequentes.
10. **Registo**: `sincronizar_producao.sh` → `verificar_seguranca.sh` → commit + etiqueta única
    `producao-AAAA-MM-DD-HHMM` → push (Mirazeite/ODOO; repositório antigo sem dados/passwords);
    documentação `.docx` do módulo + índice; memória do Claude.

## Estado final a comunicar
- **Concluída e validada** — só com os passos 1–9 cumpridos, incluindo o teste no browser (passo 7).
- **Instalada — falta a validação do Gonçalo** — quando o teste no browser não pôde ser feito pelo Claude.
- **Revertida** — se algum passo falhar e a correção não for simples e segura: repor a versão anterior (passo 1).
