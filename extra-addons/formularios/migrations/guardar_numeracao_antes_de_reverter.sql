-- Reversão do Ponto 6: correr ANTES de repor o código antigo (o Odoo apaga as colunas da numeração).
-- Guarda os números, números anteriores e histórico; ao voltar a aplicar o módulo, são repostos daqui.
DROP TABLE IF EXISTS formularios_numeracao_guardada;
CREATE TABLE formularios_numeracao_guardada AS
    SELECT 'form_reclama_cliente'::varchar AS tabela, id, name, NULL::varchar AS numeros_anteriores, NULL::text AS historico_numeracao
    FROM form_reclama_cliente
    UNION ALL
    SELECT 'form_reclama_fornecedor', id, name, numeros_anteriores, historico_numeracao
    FROM form_reclama_fornecedor;
SELECT tabela, count(*), count(name) FROM formularios_numeracao_guardada GROUP BY 1 ORDER BY 1;
