-- Reverte num_aplicar.sql: contadores e QC (42) como estavam a 26/10/2026.
-- Só reverte se nenhum número novo tiver sido usado desde a aplicação (senão voltaria a dar repetidos).
BEGIN;
DO $$
DECLARE r record;
BEGIN
  SELECT last_value, is_called INTO r FROM ir_sequence_037;
  IF NOT (r.last_value = 4 AND r.is_called) THEN RAISE EXCEPTION 'PL já foi usado desde a aplicação (%/%): não reverter', r.last_value, r.is_called; END IF;
  SELECT last_value, is_called INTO r FROM ir_sequence_038;
  IF NOT (r.last_value = 1 AND r.is_called) THEN RAISE EXCEPTION 'DL já foi usado desde a aplicação (%/%): não reverter', r.last_value, r.is_called; END IF;
  SELECT last_value, is_called INTO r FROM ir_sequence_039;
  IF NOT (r.last_value = 2 AND r.is_called) THEN RAISE EXCEPTION 'CS já foi usado desde a aplicação (%/%): não reverter', r.last_value, r.is_called; END IF;
  SELECT last_value, is_called INTO r FROM ir_sequence_041;
  IF NOT (r.last_value = 4 AND r.is_called) THEN RAISE EXCEPTION 'BA já foi usado desde a aplicação (%/%): não reverter', r.last_value, r.is_called; END IF;
  PERFORM setval('ir_sequence_037', 1, false);
  PERFORM setval('ir_sequence_038', 1, false);
  PERFORM setval('ir_sequence_039', 1, false);
  PERFORM setval('ir_sequence_041', 1, true);
  UPDATE ir_sequence SET active = true WHERE id = 42;
  RAISE NOTICE 'OK: contadores e QC (42) repostos como a 26/10/2026';
END $$;
COMMIT;
