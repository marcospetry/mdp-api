BEGIN;

CREATE TABLE IF NOT EXISTS origens_contato (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id uuid NULL REFERENCES empresas(id) ON DELETE CASCADE,
    codigo varchar(50) NOT NULL,
    nome varchar(120) NOT NULL,
    descricao text NULL,
    ativo boolean NOT NULL DEFAULT true,
    ordem integer NOT NULL,
    padrao_sistema boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_origens_contato_global_codigo ON origens_contato (upper(codigo)) WHERE empresa_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_origens_contato_empresa_codigo ON origens_contato (empresa_id, upper(codigo)) WHERE empresa_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_origens_contato_empresa ON origens_contato (empresa_id);

CREATE TABLE IF NOT EXISTS tipos_interacao (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id uuid NULL REFERENCES empresas(id) ON DELETE CASCADE,
    codigo varchar(50) NOT NULL,
    nome varchar(120) NOT NULL,
    descricao text NULL,
    ativo boolean NOT NULL DEFAULT true,
    ordem integer NOT NULL,
    padrao_sistema boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_tipos_interacao_global_codigo ON tipos_interacao (upper(codigo)) WHERE empresa_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_tipos_interacao_empresa_codigo ON tipos_interacao (empresa_id, upper(codigo)) WHERE empresa_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tipos_interacao_empresa ON tipos_interacao (empresa_id);

INSERT INTO origens_contato (empresa_id,codigo,nome,ordem,padrao_sistema)
VALUES
(NULL,'SITE','Site',1,true),(NULL,'ADMIN','Cadastro manual',2,true),(NULL,'WHATSAPP','WhatsApp',3,true),
(NULL,'INSTAGRAM','Instagram',4,true),(NULL,'EMAIL','E-mail',5,true),(NULL,'TELEFONE','Telefone',6,true),
(NULL,'VISITA_PRESENCIAL','Visita presencial',7,true),(NULL,'INDICACAO','Indicação',8,true),(NULL,'GOOGLE','Google',9,true),
(NULL,'EVENTO','Evento',10,true),(NULL,'META_ADS','Meta Ads',11,true),(NULL,'GOOGLE_ADS','Google Ads',12,true),
(NULL,'PARCERIA','Parceria',13,true),(NULL,'PROSPECCAO_ATIVA','Prospecção ativa',14,true),(NULL,'OUTRO','Outro',15,true)
ON CONFLICT DO NOTHING;

INSERT INTO tipos_interacao (empresa_id,codigo,nome,ordem,padrao_sistema)
VALUES
(NULL,'FORMULARIO_SITE','Formulário do site',1,true),(NULL,'WHATSAPP_MENSAGEM','WhatsApp - Mensagem',2,true),
(NULL,'INSTAGRAM_DIRECT','Instagram - Direct',3,true),(NULL,'INSTAGRAM_COMENTARIO','Instagram - Comentário',4,true),
(NULL,'EMAIL','E-mail',5,true),(NULL,'LIGACAO','Ligação',6,true),(NULL,'VISITA','Visita',7,true),
(NULL,'REUNIAO','Reunião',8,true),(NULL,'ANOTACAO_INTERNA','Anotação interna',9,true),(NULL,'OUTRO','Outro',10,true)
ON CONFLICT DO NOTHING;

ALTER TABLE contatos ADD COLUMN IF NOT EXISTS origem_contato_id uuid NULL REFERENCES origens_contato(id) ON DELETE RESTRICT;
ALTER TABLE interacoes ADD COLUMN IF NOT EXISTS tipo_interacao_id uuid NULL REFERENCES tipos_interacao(id) ON DELETE RESTRICT;
CREATE INDEX IF NOT EXISTS idx_contatos_origem_contato ON contatos(origem_contato_id);
CREATE INDEX IF NOT EXISTS idx_interacoes_tipo_interacao ON interacoes(tipo_interacao_id);

UPDATE contatos c SET origem_contato_id=o.id FROM origens_contato o
WHERE c.origem_contato_id IS NULL AND o.empresa_id IS NULL AND upper(o.codigo)=upper(CASE WHEN c.origem='site' THEN 'SITE' WHEN c.origem='ADMIN' THEN 'ADMIN' ELSE c.origem END);
UPDATE interacoes i SET tipo_interacao_id=t.id FROM tipos_interacao t
WHERE i.tipo_interacao_id IS NULL AND t.empresa_id IS NULL AND upper(t.codigo)=upper(i.tipo_interacao);

COMMIT;
