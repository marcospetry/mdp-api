BEGIN;

-- MDP - Migration 005
-- Inclui PROSPECCAO como situação comercial/relacional de empresa.
-- Não altera tabela ou coluna; apenas a restrição dos valores permitidos.

ALTER TABLE empresas
    DROP CONSTRAINT IF EXISTS ck_empresas_status;

ALTER TABLE empresas
    ADD CONSTRAINT ck_empresas_status
    CHECK (status IN ('PROSPECCAO', 'EM_AVALIACAO', 'CLIENTE', 'DESCARTADA'));

COMMENT ON COLUMN empresas.status IS
    'Situação comercial/relacional da empresa: PROSPECCAO, EM_AVALIACAO, CLIENTE ou DESCARTADA. Independente do status de diagnosticos.';

COMMIT;
