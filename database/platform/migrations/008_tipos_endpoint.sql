BEGIN;

CREATE TABLE tipos_endpoint (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo VARCHAR(50) NOT NULL UNIQUE,
    nome VARCHAR(100) NOT NULL,
    descricao TEXT,
    ordem INTEGER NOT NULL DEFAULT 0,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE tipos_endpoint OWNER TO mdp;

INSERT INTO tipos_endpoint (codigo,nome,descricao,ordem,ativo) VALUES
('SITE','Site','Site ou domínio público do Tenant.',10,true),
('FORMULARIO','Formulário','Formulário público pertencente ao Tenant.',20,true),
('EMAIL','E-mail','Endereço de e-mail público do Tenant.',30,true),
('TELEFONE','Telefone','Número de telefone público do Tenant.',40,true),
('WHATSAPP','WhatsApp','Canal WhatsApp pertencente ao Tenant.',50,true),
('INSTAGRAM','Instagram','Perfil Instagram pertencente ao Tenant.',60,true),
('FACEBOOK','Facebook','Página Facebook pertencente ao Tenant.',70,true),
('OMNI_LINK','Omni Link','Link público Omni pertencente ao Tenant.',80,true)
ON CONFLICT (codigo) DO NOTHING;

ALTER TABLE tenant_endpoints ADD COLUMN tipo_endpoint_id UUID;
UPDATE tenant_endpoints te
SET tipo_endpoint_id = t.id
FROM tipos_endpoint t
WHERE t.codigo = te.tipo;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM tenant_endpoints WHERE tipo_endpoint_id IS NULL) THEN
    RAISE EXCEPTION 'Existem tenant_endpoints com tipo sem correspondencia em tipos_endpoint.';
  END IF;
END $$;

ALTER TABLE tenant_endpoints ALTER COLUMN tipo_endpoint_id SET NOT NULL;
ALTER TABLE tenant_endpoints ADD CONSTRAINT fk_tenant_endpoints_tipo
  FOREIGN KEY (tipo_endpoint_id) REFERENCES tipos_endpoint(id) ON DELETE RESTRICT;

DROP INDEX IF EXISTS idx_tenant_endpoints_tipo_identificador;
CREATE INDEX idx_tenant_endpoints_tipo_identificador
  ON tenant_endpoints(tipo_endpoint_id, identificador_externo)
  WHERE ativo = TRUE;

ALTER TABLE tenant_endpoints DROP COLUMN tipo;

COMMIT;
