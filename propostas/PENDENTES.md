# Pendentes para investigação (sincronização Primavera → Odoo)

Registado a 27/10/2026, depois da correcção do ponto 2 (linhas de faturas a 0 € que entravam a 1 €).
Nada disto foi alterado; cada ponto deve ser analisado e autorizado à parte.

## Fatura lançada com linha a 1 € (excluída do ponto 2)
- **FAT/2026/185** (lançada no Odoo; linha 14409, palete PAL.1200.0800.02 a 1,00 € — no Primavera 0 €). Total no Odoo 5.512,00 €.
  Corrigir exige voltar a rascunho (mexe na contabilidade do Odoo). Decisão do user: pendente.

## 16 faturas com IVA diferente do Primavera (já existia antes do ponto 2)
FA/2026/174, FA/2026/175, FA/2026/184, FA/2026/185, FA/2026/186, FA/2026/187, FA/2026/189, FA/2026/197,
FA/2026/198, FA/2026/200, FAT/2026/192, FAT/2026/194, FAT/2026/195, FAT/2026/201, FAT/2026/202, FAT/2026/206.
Ex.: FA/2026/198 — IVA 1.068,58 € no Odoo, 301,58 € no Primavera. Provável escolha errada da taxa (a investigar).

## 6 faturas FAT com uma linha sem artigo
FAT/2026/202 (OL.008.30.05000.01), FAT/2026/347, FAT/2026/371, FAT/2026/403, FAT/2026/426 (CAPS.38.01.11.11),
FAT/2026/402 (OL.005.31.03000.02). O artigo ainda não existia no Odoo quando a fatura foi importada (hoje já existe);
quantidade e preço da linha estão certos.

## 4 diferenças de arredondamento de 1 cêntimo (já existiam)
FA/2026/73 (41.769,50 vs 41.769,51), FA/2026/171 (57.133,18 vs 57.133,17), FAT/2026/105 (12.463,71 vs 12.463,72),
FA/2026/206 (42.501,46 vs 42.501,45) — total sem IVA Odoo vs Primavera.

## Arredondamentos aceites (ponto 3, 27/10/2026)
37 documentos com 1–2 cêntimos de diferença face ao Primavera só por método de cálculo (mesmas quantidades, preços, descontos e taxas):
Primavera arredonda bruto e desconto em separado e o IVA linha a linha; o Odoo arredonda o subtotal e o IVA no total (round_globally). Aceite pelo user.

## IVA: FA/2026/176 junta-se às 16
FA/2026/176 — IVA 23% no Odoo vs 6% no Primavera desde a importação (Maio); a correcção dos descontos reduziu a diferença (602,78 → 586,59 €). Uma reimportação no ensaio corrigiu o IVA (pista).

## Pontos já combinados, por ordem
3. ~~Descontos~~ — aplicado 27/10/2026.
4. Clientes/fornecedores anulados não arquivados (FO0160, FO0792).
5. Fichas sobrescritas pela volta nocturna por NIF partilhado (MARIN TRADING e outras 4).
6. Casas decimais do peso (3 ou 5).

## Outros
- Packing Lists antigas com modo de transporte "Outro" (fora da lista) — botão Duplicar falha.
- Numeração dos documentos não recomeça por ano.
