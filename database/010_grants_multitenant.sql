BEGIN;

-- Permissoes das estruturas multi-tenant para o role usado pela aplicacao.
-- Necessario apos a criacao das tabelas pelas migrations 007 e 008.
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE tenants TO mdp;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE usuarios_tenants TO mdp;

COMMIT;
