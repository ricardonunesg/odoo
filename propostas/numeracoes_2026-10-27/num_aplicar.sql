-- Numerações dos documentos (proposta 27/10/2026):
--  * contadores a seguir ao maior número já emitido (os documentos existentes não mudam):
--      PL (37) → próximo 0005 | DL (38) → 0002 | CS (39) → 0003 | BA (41) → 0005
--  * CQ/QC partilham o código 'certificado.qualidade': fica activa a CQ (40, a que o Odoo usa hoje)
--    e a QC (42) é arquivada (não apagada). Nenhum certificado de qualidade foi numerado.
-- Só avança se tudo estiver exactamente no estado de 26/10/2026; senão cancela tudo.
BEGIN;
DO $$
DECLARE r record;
BEGIN
  SELECT last_value, is_called INTO r FROM ir_sequence_037;
  IF NOT (r.last_value = 1 AND NOT r.is_called) THEN RAISE EXCEPTION 'PL: contador mudou (%/%), nada alterado', r.last_value, r.is_called; END IF;
  SELECT last_value, is_called INTO r FROM ir_sequence_038;
  IF NOT (r.last_value = 1 AND NOT r.is_called) THEN RAISE EXCEPTION 'DL: contador mudou (%/%), nada alterado', r.last_value, r.is_called; END IF;
  SELECT last_value, is_called INTO r FROM ir_sequence_039;
  IF NOT (r.last_value = 1 AND NOT r.is_called) THEN RAISE EXCEPTION 'CS: contador mudou (%/%), nada alterado', r.last_value, r.is_called; END IF;
  SELECT last_value, is_called INTO r FROM ir_sequence_041;
  IF NOT (r.last_value = 1 AND r.is_called) THEN RAISE EXCEPTION 'BA: contador mudou (%/%), nada alterado', r.last_value, r.is_called; END IF;
  IF (SELECT count(*) FROM ir_sequence WHERE id = 42 AND active AND code = 'certificado.qualidade' AND prefix = 'QC/%(year)s/') <> 1 THEN
    RAISE EXCEPTION 'QC (42) não está no estado esperado, nada alterado';
  END IF;
  PERFORM setval('ir_sequence_037', 4, true);   -- PL próximo 5
  PERFORM setval('ir_sequence_038', 1, true);   -- DL próximo 2
  PERFORM setval('ir_sequence_039', 2, true);   -- CS próximo 3
  PERFORM setval('ir_sequence_041', 4, true);   -- BA próximo 5
  UPDATE ir_sequence SET active = false WHERE id = 42;
  RAISE NOTICE 'OK: PL→5, DL→2, CS→3, BA→5; QC (42) arquivada';
END $$;
COMMIT;
