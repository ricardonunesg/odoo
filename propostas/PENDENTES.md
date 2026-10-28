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
4. ~~Clientes/fornecedores anulados~~ — aplicado 27/10/2026 (FO0160 e FO0792 arquivados).
5. ~~Fichas sobrescritas por NIF partilhado~~ — aplicado 28/10/2026 (correcção alargada: cliente↔fornecedor na mesma ficha; 7 fichas novas 3820–3826).
6. ~~Casas decimais do peso~~ — alteração A aplicada 28/10/2026 12:33 (linhas de documentos 5 casas peso / 9 volume). Peso líquido integrado aplicado 28/10/2026 14:11 (primavera_connector 18.0.2.4.0 com -u).

## Outros
- Packing Lists antigas com modo de transporte "Outro" (fora da lista) — botão Duplicar falha.
- Numeração dos documentos não recomeça por ano.

## Do ponto 5 (28/10/2026) — decisões do user: não mexer agora
- Histórico: as 4.597 alterações falsas antigas (MARIN 1754, HEBRUMEL 1851, …) ficam como estão — não apagar.
- Códigos duplicados no Primavera (CL0027/CL0056/CL0062 com NIF MZ0, CL0109↔CL0128, CL0119↔CL0137, CL0171↔CL0181, CL0455↔CL0760): não anular; análise posterior.
- ECL/2026/427: entidade CL0647 no Primavera, CL0001 no Odoo — investigar à parte, sem alterar.
- Empresas com ficha de cliente e ficha de fornecedor separadas (antes da correcção): GARLAND (CL0905 ficha 3566 / FO0220 ficha 2853),
  RAMAGPLAST (CL0909 3624 / FO0858 3449), RCINOXSERVE (CL0841 2594 / FO0877 3573) — não juntar agora.
- Ficha MIRAZEITE, SA (CL0000, 1725): morada com 2.ª linha no Odoo; a volta nunca passa no CL0000 (começa em CL0001) — sem efeito, só registo.

## Do ponto 6 (28/10/2026) — não alterado, para decisão
- Documentos antigos NÃO corrigidos (decisão do user): faturas Odoo são cópias em rascunho do Primavera; 12 com diferença ≥0,5 % (maior FAT/2026/440 +2,9 %, FA/2026/301 −26,46 kg); 9 PL confirmadas com ≤0,15 % de diferença.
- PL/2026/0001 (id 36, FA/2026/171, rascunho) e "Novo" (id 35): peso líquido das OLIV = bruto (+1.874,88 kg). Corrige-se ao recarregar a PL depois da alteração C.
- 19 ECLs anuladas (34 linhas) ficam com pesos arredondados: a re-sync não mexe nas linhas de ECLs anuladas.
- Primavera: 132 artigos activos com PesoLiquido mas sem Peso (bruto) — ex. EMB.01.021.10000.40, EMB.01.002.01000.01 → peso bruto 0 nos documentos (FAT/2026/47: líquido > bruto). Corrigir no Primavera.
- Primavera: linhas de ECL com peso líquido escrito igual ao bruto (ECL/2026/539, 537, 498, 449, 434, 377, 355) — corrigir no Primavera se for engano.
- Certificado de qualidade soma as paletes no peso líquido total (ex. +575 kg na FA/2026/171) — PL, boletins e certificado de salubridade excluem-nas. Já era assim.

## Do peso líquido (28/10/2026)
- PL/2026/0001 (id 36) e "Novo" (id 35) NÃO recarregadas — decisão do Gonçalo à parte (recarregar → líquido 16.733,628 → 14.282,748 kg).
- Primavera: preencher Peso (bruto) nos 132 artigos assinalados ("Pesos incompletos no Primavera") e PesoLiquido em DIV.0002, DIV.0003, MERC.0005, MERC.0006.
