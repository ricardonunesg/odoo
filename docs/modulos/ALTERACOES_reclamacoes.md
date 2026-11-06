# Alterações — Formulários e Qualidade (reclamações)

Cópias dos documentos oficiais em `/srv/partilhada/Modulos ODOO_Relatórios/` (3.Formularios.docx,
10. Qualidade_Reclamacoes.docx, 0.Indice_Modulos.docx), guardadas aqui para histórico.

## Estado atual em produção (06/11/2026)

- Qualidade 18.0.1.12.0 e Formulários 18.0.1.5.3. Fases 1 e 2 concluídas.
- Notificações ATIVAS para Clientes, Fornecedores e Internas: Ricardo Machado responsável, Rita Faroleira informada.
- Prazo de 7 dias apenas informativo, sem lembretes automáticos. As reclamações não criam Activities.
- Depois de atualizar módulos com JavaScript é preciso recarregar a página do Odoo (F5).

**Ordem de implementação:** Reclamações Internas (31/10) · Fase 1: só administradores apagam (31/10), reorganização
do código (31/10), numeração RCL/RFO/RIN (01/11), filtros e pesquisa (01/11), artigos no Dashboard (01/11) ·
Fase 2: ficha do Responder (01/11), pré-visualização de anexos (01/11), artigos e colunas nas listas (02/11),
rastreabilidade de clientes e lotes nos Formulários (02/11), notificações no Discuss (05/11). Depois das fases:
agrupar por Cliente/Fornecedor, Artigo e Lote (06/11).

**Previsto, ainda não existe:** Pendentes no Discuss (Por tratar, Por aprovar, filtro Atrasados), independentes das
Activities; rastreabilidade de Fornecedores e Internas.

## 06/11/2026 — Formulários: lista de lotes no próprio campo Lote (formularios 18.0.1.5.3)

- O campo Lote das reclamações de clientes abre, ao clicar, os lotes faturados ao cliente (lote, documento e data) e
  filtra ao escrever. Sem botão separado e sem salto da página ao escolher. Escrita manual mantida.
- A consulta ao Primavera não mudou. Sem lotes ou com o Primavera indisponível: aviso e escrita manual.
- Ensaio isolado: browser 13/13. Produção (06/11 19:03, commit 4d4a2c5): só os Formulários, 0 erros, browser 7/7 sem gravar.
- Reversão: repor os ficheiros da versão 2204e79 (backups *2026-11-06_pre-lote*), apagar lote_primavera_field.scss;
  -u formularios; F5.

## 06/11/2026 — Agrupar por Cliente/Fornecedor, Artigo e Lote (qualidade_reclamacoes 18.0.1.12.0)

- 3 novos agrupamentos nas listas de Clientes, Fornecedores e Internas; os 8 existentes mantêm-se.
- Artigo = "código — descrição atual do Primavera"; agrupa pelo código. Cada reclamação fica num único grupo: com vários
  artigos ou lotes forma um grupo próprio com todos juntos, sem duplicar nem perder informação.
- 2 valores guardados por reclamação, preenchidos por SQL na migração, sem mudar o Modificado por/em.
- Produção (06/11 18:44, commit 2204e79): só a Qualidade, 0 erros, 19/19, dados e indicadores iguais.
- Reversão: repor os ficheiros da versão 722f42a (backups *2026-11-06_pre-grupos*), apagar migrations/18.0.1.12.0/;
  -u qualidade_reclamacoes. Ensaiada: 0 erros, Modificado por/em igual.

## 05/11/2026 — Fase 2, Ponto 5: ativação das notificações (sem alteração de código)

- Ativados em produção os 3 tipos (Clientes, Fornecedores, Internas), com autorização do Gonçalo: Ricardo, Rita, 7 dias.
- Só a opção Ativo da configuração. Sem Activities, sem notificações retroativas, dados e indicadores iguais.
- Desligar sem reverter: pôr os tipos em Inativo em Qualidade → Configuração → Responsáveis e notificações.

## 05/11/2026 — Fase 2, Ponto 5: só notificações, sem Activities (qualidade_reclamacoes 18.0.1.11.0)

- Decisão: as reclamações não criam Activities (ficam para lembretes e follow-ups). Retirados a atividade, a conclusão
  automática e o tipo "Tratar reclamação". Com o tipo ativo: 1 notificação ao responsável ("Nova reclamação para
  tratar") e 1 a cada informado ("Nova reclamação"), com link "Abrir no Responder". Prazo guardado para uso futuro.
- Produção (05/11 22:47, commit 722f42a): só a Qualidade, 0 erros; instalada com os 3 tipos inativos (ativados depois,
  ver entrada acima); dados, indicadores, numeração e Activities iguais; verificação 10/10 + pacote JS.
- Reversão: /home/odoo/backups/REVERSAO_f2p5_notificacoes.md

## 05/11/2026 — Fase 2, Ponto 5 (1.ª versão, SUBSTITUÍDA pela 18.0.1.11.0, sem Activities): atividades e avisos (qualidade_reclamacoes 18.0.1.10.0)

- Menu Qualidade → Configuração → Responsáveis e notificações (3 linhas, só administradores): ativo, responsável,
  informados e prazo por tipo. Instalado com os 3 tipos DESATIVADOS (Ricardo, Rita, 7 dias).
- Atividade única "Tratar reclamação" na reclamação, aviso aos informados, link "Abrir no Responder", conclusão
  automática em Fechado, nova atividade ao reabrir, botão Responder na ficha da reclamação. Emails formais iguais.
- Produção (05/11 21:16, commit 8b7c8c3): só a Qualidade, 0 erros; dados, indicadores e numeração iguais.
- Reversão: /home/odoo/backups/REVERSAO_f2p5_notificacoes.md

## 02/11/2026 — Fase 2, Ponto 4c: "Artigo / lote reclamado" com a descrição (formularios 18.0.1.5.2)

- A linha de artigo aparece como "descrição actual do artigo no Primavera — lote" (artigos sincronizados no Odoo;
  sem artigo com esse código, a descrição gravada). O código continua a ser usado nas consultas.
- Produção (02/11 22:23, commits 8af60c3 + efb3f8e): só Formulários, 0 erros; 44/44 linhas com a descrição do
  Primavera (2 códigos antigos mal escritos mostram a descrição gravada); RCL/2026/0024 consulta o artigo/lote certos.
- Reversão: repor formularios/models/form_cliente_linha.py e __manifest__.py da versão 4f8ed5a (backups *pre-f2p4c*);
  -u formularios.

## 02/11/2026 — Fase 2, Ponto 4b: Rastreabilidade no topo do Responder (qualidade_reclamacoes 18.0.1.9.1)

- Interruptor "Rastreabilidade" logo abaixo de "Imprimir PDF da reclamação": liga = mostra por baixo, desliga =
  recolhe; separador antigo no fundo retirado. Só vista XML; consultas ao Primavera iguais; não grava respostas.
- Produção (02/11 22:15, commit 4f8ed5a): só a Qualidade, 0 erros, verificação 9/9, dados iguais.
- Reversão: repor a vista da versão 26fad0b (backups *pre-f2p4b*) e -u qualidade_reclamacoes.

## 02/11/2026 — Fase 2, Ponto 4: rastreabilidade de clientes (formularios 18.0.1.5.0, qualidade_reclamacoes 18.0.1.9.0)

- Separador "Rastreabilidade" no Responder (clientes): COM do lote (data da COM), consumos reais só do produto
  reclamado (IdLinhaComposto), origem dos materiais até 2 níveis (fatura/guia do fornecedor: confirmada por
  LinhasComprasTrans, senão "provável"), clientes por FA/FAT/FRT, devoluções à parte; avisos de lote genérico,
  mistura, sem entrada, lote não encontrado, guias sem fatura e destino potencialmente incompleto (lotações
  intermédias). Página "outros produtos acabados" por lote de material. Consulta só a pedido; nada gravado.
- Formulários: botão de lotes faturados ao cliente no campo Lote (escrita manual mantida).
- Primavera só leitura: formularios.primavera.leitura recusa tudo o que não seja SELECT; 5 s por consulta.
- Produção (02/11 21:27, commit 26fad0b): só Formulários + Qualidade, 0 erros, verificação 25/25 + 9/9 + 2/2,
  dados iguais antes/depois, nenhuma resposta gravada.
- Reversão: /home/odoo/backups/REVERSAO_f2p4_rastreabilidade.md

## 02/11/2026 — Fase 2, Ponto 3: artigos e colunas nas listas (qualidade_reclamacoes 18.0.1.8.0)

- Listas Clientes / Fornecedores / Internas: Código Artigo, Descrição Artigo e Lote vêm das linhas de artigos (um por
  linha na mesma célula, alinhados; sem linhas, campos antigos). Campos calculados, nada gravado na BD.
- Visíveis por defeito: Número, Criado em, Cliente/Fornecedor, Código, Descrição, Lote, Estado, Origem, Responder;
  restantes opcionais (⋮). Filtros, pesquisas e agrupamentos inalterados. Preferências: Favoritos (servidor) e
  colunas (browser), nativos do Odoo.
- Produção (02/11 11:17, commit 78f6bb9): só a Qualidade, 0 erros na actualização, 61/61 reclamações certas
  (4 com vários artigos), 13/13 + browser 6/6; mudam só as 2 listas, 9 campos novos e a versão.
- Reversão: /home/odoo/backups/REVERSAO_f2p3_listas.md

## 01/11/2026 — Fase 2, Ponto 2: pré-visualização de anexos (qualidade_reclamacoes 18.0.1.7.0)

- Ficha do Responder: anexos do formulário e evidências da Qualidade abrem no visualizador nativo do Odoo
  (imagens, PDF, vídeo); Excel, Word, ZIP e links do Google Drive como antes; permissões iguais.
- Esc / botão X fecham só o visualizador (a ficha e o texto por gravar mantêm-se).
- Produção (01/11 23:30, commit 07e7f7c): só a Qualidade, 0 erros na actualização, verificação no browser 9/9,
  nenhuma resposta gravada pela verificação; mudam só as 2 vistas das respostas e a versão.
- Reversão: /home/odoo/backups/REVERSAO_f2p2_anexos.md

## 01/11/2026 — Fase 2, Ponto 1: ficha do Responder (qualidade_reclamacoes 18.0.1.6.0)

- Campo "Reclamação" da resposta só de leitura (sem abrir a ficha dos Formulários nem escolher outra); o servidor
  recusa mudar uma resposta para outra reclamação.
- Link "Imprimir PDF da reclamação" na ficha do Responder: abre o PDF noutro separador, também numa resposta por
  gravar, sem criar respostas; sem sessão iniciada leva ao login.
- Produção (01/11 20:16, commit 219b23f): só a Qualidade, 0 erros novos, históricos/indicadores/numerações iguais,
  testes 31/31 (+ P11 47/47, P5 11/11, P1 25/25).
- Reversão: /home/odoo/backups/REVERSAO_f2p1_resposta.md

## 01/11/2026 — Ponto 5: artigos no Dashboard (qualidade_reclamacoes 18.0.1.5.0)

- O painel passa a mostrar todos os artigos das linhas de cada reclamação (antes: campo antigo do cabeçalho, 25 de 61
  sem artigo). Uma linha por reclamação: totais e indicadores iguais. Pesquisa "Artigo" por código ou descrição.
- Sem submenu "Por Artigo" nem ecrãs, campos ou tabelas novos (decisão do Gonçalo).
- Ensaio isolado e produção (01/11 19:23, commit 24555a2): só a Qualidade, 0 erros, 61/61 com todos os artigos
  (0 sem artigo), indicadores iguais (Total 61, 78,7 %), históricos idênticos, P5 11/11, P11 47/47, P1 25/25.
- O teste antigo das internas (31/10) tem 7 verificações com referências desactualizadas pelo Ponto 6 (assunto sem
  número, referência "Interna #"); o comportamento real está coberto pelos testes do Ponto 6.
- Reversão: /home/odoo/backups/REVERSAO_p5_artigos.md

## 01/11/2026 — Ponto 11: filtros, pesquisa e agrupamentos na Qualidade (qualidade_reclamacoes 18.0.1.4.0)

- 3 listas (Clientes, Fornecedores, Internas): filtros por estado, gravidade, categoria, "as minhas", datas de criação,
  conclusão e fecho; pesquisa por número, entidade, responsável, artigo e lote (todas as linhas); agrupar por estado,
  gravidade, categoria, responsável, armazém, mês/trimestre/ano. Sem menus nem fichas novas; Responder igual.
- 8 valores da última resposta guardados (actualizam-se ao criar/alterar/eliminar respostas); preenchidos por SQL na
  migração para não mudar o Criado/Modificado por/em dos históricos. Daqui para a frente o Modificado por/em da
  reclamação mostra também o engenheiro que mexeu nas respostas (utilizador real, confirmado com logins reais).
- Ensaio: 47/47, históricos idênticos, simultaneidade, reversão. Produção (01/11 19:00, commit 7bc6697): só a Qualidade
  actualizada, 0 erros, históricos idênticos, 61/61 valores = respostas, 47/47, P1 25/25, captura igual (salvo ids).
- Reversão: /home/odoo/backups/REVERSAO_p11_filtros.md

## 01/11/2026 — Ponto 6: numeração RCL / RFO / RIN (formularios 18.0.1.4.0, qualidade_reclamacoes 18.0.1.3.0)

- Número automático e anual, sem saltos nem repetidos: RCL (clientes), RFO (fornecedores), RIN (internas); faixas 2026-2035.
- Atribuído ao gravar, antes do PDF e do email: assunto, corpo, título do PDF e nome do ficheiro PDF.
- 61 históricas numeradas por data de criação (lista em /home/odoo/backups/mapa_numeracao_historica_2026-10-31.csv).
- "Corrigir tipo" (só administradores): motivo + confirmação, número novo do ano original, números anteriores pesquisáveis.
- Ensaio isolado: 66/66, simultaneidade sem repetidos/buracos, 2.ª actualização sem recuo, reversão com números repostos.
- Produção (01/11 18:16, commit ca2d9eb): 61/61 iguais à lista, dados históricos idênticos, contadores 36/27/1, 0 erros.
  1.ª tentativa de cópia falhou (3 ficheiros de root, iguais nas duas versões) e foi revertida antes de qualquer alteração.
- Testes reais: TESTE-RCL/2026/0001, TESTE-RFO/2026/0001, TESTE-RIN/2026/0001 (números de teste em memória; email só para o
  Gonçalo; contadores oficiais intactos). Ficam em produção para o Gonçalo experimentar e apagar.
- Reversão: /home/odoo/backups/REVERSAO_p6_numeracao.md (começa por guardar_numeracao_antes_de_reverter.sql).

## 31/10/2026 — Ponto 12: reorganização do código (formularios 18.0.1.3.0, qualidade_reclamacoes 18.0.1.2.0)

- Sem alteração de funcionamento: formulários, respostas, menus, vistas, PDFs, emails, painéis, permissões e dados iguais.
- `constantes.py` em cada módulo (emails, armazéns, instalações, estados, categorias, origens, gravidades).
- Bases comuns sem tabela: `formularios.reclamacao.base`, `qualidade.resposta.base`, `qualidade.ultima.resposta.mixin`;
  SQL do Dashboard gerado de um só bloco. Linhas de artigo mantidas como estavam.
- Ensaio A/B isolado: 291/291 itens iguais; esquema igual (só metadados das 3 bases); PDFs reais iguais;
  concorrência (2 utilizadoras + 2 engenheiros em simultâneo), anexos, reinício e sessões novas iguais; reversão ensaiada.
- Produção (31/10 12:25, commit f42110a): actualização sem erros; fotografia antes/depois só com versões e as 32
  descrições de campos das bases; crons, numerações e contadores iguais; captura 291/291 igual à referência do código
  antigo; Ponto 1 25/25; 0 erros novos nos registos.
- Backups e reversão: `/home/odoo/backups/*2026-10-31_pre-p12*` e `/home/odoo/backups/REVERSAO_p12_reorganizacao_2026-10-31.md`.

## 31/10/2026 — formularios 18.0.1.2.0: só Administradores apagam reclamações

- Reclamações de clientes, fornecedores e internas: apagar só para `base.group_system` (Administradores).
  Todos os utilizadores continuam a criar, ver e editar.
- Linhas de artigos: sem alteração (continuam a poder ser retiradas/corrigidas durante o preenchimento).
- Respostas da Qualidade: sem alteração (engenheiros da Qualidade criam, editam e eliminam).
- Aplicado no servidor (`ir.model.access`): o pedido de apagar é recusado mesmo fora do ecrã.
- Ensaio isolado: 33/33 testes + teste via web; produção: 25/25 verificações; fotografia antes/depois só
  com as 2 permissões alteradas, 2 novas e a versão.
- Backups e reversão: `/home/odoo/backups/*2026-10-31_pre-p1-eliminacao*` e
  `/home/odoo/backups/REVERSAO_p1_eliminacao_2026-10-31.md`.

## 31/10/2026 — 18.0.1.1.0: reclamações internas (Arruda ↔ Tomar)

- Tipo Externa/Interna nas reclamações de fornecedor; menu e painel "Internas" na Qualidade.
