BEGIN;

INSERT INTO origens_contato (empresa_id,codigo,nome,ordem,padrao_sistema)
VALUES
(NULL,'OMNI','Omni',16,true)
ON CONFLICT DO NOTHING;

INSERT INTO tipos_interacao (empresa_id,codigo,nome,ordem,padrao_sistema)
VALUES
(NULL,'OMNI_AGENDAMENTO','Omni - Agendamento',11,true)
ON CONFLICT DO NOTHING;

COMMIT;
