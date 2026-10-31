# Alterações — Formulários e Qualidade (reclamações)

Cópias dos documentos oficiais em `/srv/partilhada/Modulos ODOO_Relatórios/` (3.Formularios.docx,
10. Qualidade_Reclamacoes.docx, 0.Indice_Modulos.docx), guardadas aqui para histórico.

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
