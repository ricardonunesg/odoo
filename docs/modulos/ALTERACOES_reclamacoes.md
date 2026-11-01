# Alterações — Formulários e Qualidade (reclamações)

Cópias dos documentos oficiais em `/srv/partilhada/Modulos ODOO_Relatórios/` (3.Formularios.docx,
10. Qualidade_Reclamacoes.docx, 0.Indice_Modulos.docx), guardadas aqui para histórico.

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
