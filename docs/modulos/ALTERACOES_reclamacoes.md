# Alterações — Formulários e Qualidade (reclamações)

Cópias dos documentos oficiais em `/srv/partilhada/Modulos ODOO_Relatórios/` (3.Formularios.docx,
10. Qualidade_Reclamacoes.docx, 0.Indice_Modulos.docx), guardadas aqui para histórico.

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
