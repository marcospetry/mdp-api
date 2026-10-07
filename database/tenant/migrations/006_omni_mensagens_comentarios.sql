-- 006_omni_mensagens_comentarios.sql
-- Aplicar nos bancos de TENANT (tenant_mdp e tenant demo). NAO aplicar em mdp_platform nem em mdp (legado).
-- Validar primeiro em DEV. Idempotente.
--
-- Escopo MINIMO para Instagram e Facebook (Inbox + Comments do App Review).
-- Nao depende de contatos/interacoes (CRM): a ligacao com o CRM entra depois, como coluna nova.
-- endpoint_id aponta para mdp_platform.tenant_endpoints.id (outro banco): sem FK por desenho.
BEGIN;

-- ---------------------------------------------------------------------------
-- Conversas (DM do Instagram / Messenger)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS omni_conversas (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canal                       VARCHAR(20)  NOT NULL,
    endpoint_id                 UUID         NOT NULL,
    participante_externo_id     VARCHAR(255) NOT NULL,
    participante_nome           VARCHAR(255),
    participante_usuario        VARCHAR(255),
    status                      VARCHAR(20)  NOT NULL DEFAULT 'ABERTA',
    nao_lidas                   INTEGER      NOT NULL DEFAULT 0,
    ultima_mensagem_em          TIMESTAMPTZ,
    ultima_mensagem_cliente_em  TIMESTAMPTZ,
    created_at                  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_omni_conversas_canal  CHECK (canal IN ('INSTAGRAM', 'FACEBOOK')),
    CONSTRAINT ck_omni_conversas_status CHECK (status IN ('ABERTA', 'ARQUIVADA')),
    CONSTRAINT ck_omni_conversas_nao_lidas CHECK (nao_lidas >= 0),
    CONSTRAINT uq_omni_conversas_participante UNIQUE (endpoint_id, participante_externo_id)
);
ALTER TABLE omni_conversas OWNER TO mdp;
CREATE INDEX IF NOT EXISTS idx_omni_conversas_recentes
    ON omni_conversas (endpoint_id, ultima_mensagem_em DESC NULLS LAST);

COMMENT ON COLUMN omni_conversas.ultima_mensagem_cliente_em IS
    'Base da janela de 24h para responder DM no Instagram/Messenger.';

-- ---------------------------------------------------------------------------
-- Mensagens
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS omni_mensagens (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversa_id              UUID        NOT NULL REFERENCES omni_conversas(id) ON DELETE CASCADE,
    direcao                  VARCHAR(10) NOT NULL,
    external_message_id      VARCHAR(255),
    tipo                     VARCHAR(20) NOT NULL DEFAULT 'TEXTO',
    texto                    TEXT,
    status_envio             VARCHAR(20) NOT NULL DEFAULT 'RECEBIDA',
    erro                     TEXT,
    enviado_por_usuario_id   UUID,
    ocorrida_em              TIMESTAMPTZ NOT NULL,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_omni_mensagens_direcao CHECK (direcao IN ('ENTRADA', 'SAIDA')),
    CONSTRAINT ck_omni_mensagens_status  CHECK (status_envio IN ('RECEBIDA', 'ENVIADA', 'FALHA'))
);
ALTER TABLE omni_mensagens OWNER TO mdp;
CREATE UNIQUE INDEX IF NOT EXISTS uq_omni_mensagens_externa
    ON omni_mensagens (conversa_id, external_message_id) WHERE external_message_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_omni_mensagens_conversa
    ON omni_mensagens (conversa_id, ocorrida_em);

COMMENT ON COLUMN omni_mensagens.enviado_por_usuario_id IS
    'mdp_platform.usuarios.id de quem respondeu pelo Omni (sem FK: outro banco).';
COMMENT ON COLUMN omni_mensagens.external_message_id IS
    'ID da mensagem na Meta (idempotencia: o webhook pode repetir o evento).';

-- ---------------------------------------------------------------------------
-- Comentarios (posts do Instagram / Pagina do Facebook) e as respostas enviadas pelo Omni
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS omni_comentarios (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canal                    VARCHAR(20)  NOT NULL,
    endpoint_id              UUID         NOT NULL,
    external_comment_id      VARCHAR(255) NOT NULL,
    parent_external_id       VARCHAR(255),
    post_external_id         VARCHAR(255),
    post_resumo              TEXT,
    post_permalink           TEXT,
    origem                   VARCHAR(10)  NOT NULL DEFAULT 'EXTERNO',
    autor_externo_id         VARCHAR(255),
    autor_nome               VARCHAR(255),
    autor_usuario            VARCHAR(255),
    texto                    TEXT,
    respondido               BOOLEAN      NOT NULL DEFAULT FALSE,
    enviado_por_usuario_id   UUID,
    status_envio             VARCHAR(20),
    erro                     TEXT,
    ocorrido_em              TIMESTAMPTZ  NOT NULL,
    created_at               TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_omni_comentarios_canal  CHECK (canal IN ('INSTAGRAM', 'FACEBOOK')),
    CONSTRAINT ck_omni_comentarios_origem CHECK (origem IN ('EXTERNO', 'PROPRIO')),
    CONSTRAINT ck_omni_comentarios_envio  CHECK (status_envio IS NULL OR status_envio IN ('ENVIADA', 'FALHA')),
    CONSTRAINT uq_omni_comentarios_externo UNIQUE (endpoint_id, external_comment_id)
);
ALTER TABLE omni_comentarios OWNER TO mdp;
CREATE INDEX IF NOT EXISTS idx_omni_comentarios_recentes
    ON omni_comentarios (endpoint_id, ocorrido_em DESC);
CREATE INDEX IF NOT EXISTS idx_omni_comentarios_post
    ON omni_comentarios (endpoint_id, post_external_id);
CREATE INDEX IF NOT EXISTS idx_omni_comentarios_autor
    ON omni_comentarios (endpoint_id, autor_externo_id);

COMMENT ON COLUMN omni_comentarios.origem IS
    'EXTERNO = comentario recebido; PROPRIO = resposta enviada pelo Omni (parent_external_id = comentario respondido).';

-- ---------------------------------------------------------------------------
-- Permissoes e perfil do Omni (dados, sem codigo): perfil enxuto para usuarios de revisao/operacao
-- ---------------------------------------------------------------------------
INSERT INTO permissoes (codigo, nome, descricao, ativo) VALUES
    ('OMNI_INTEGRACOES', 'Omni - Integracoes', 'Conectar, reconectar e desconectar canais (Instagram, Facebook).', TRUE),
    ('OMNI_INBOX',       'Omni - Inbox',       'Ver e responder mensagens diretas dos canais conectados.',        TRUE),
    ('OMNI_COMENTARIOS', 'Omni - Comentarios', 'Ver e responder comentarios dos canais conectados.',             TRUE)
ON CONFLICT (codigo) DO NOTHING;

INSERT INTO perfis (codigo, nome, descricao, ativo, acesso_total) VALUES
    ('OMNI_OPERADOR', 'Operador Omni', 'Acesso apenas a Integracoes, Inbox e Comentarios do Omni.', TRUE, FALSE)
ON CONFLICT (codigo) DO NOTHING;

INSERT INTO perfis_permissoes (perfil_id, permissao_id)
SELECT p.id, pm.id
  FROM perfis p
  JOIN permissoes pm ON pm.codigo IN ('OMNI_INTEGRACOES', 'OMNI_INBOX', 'OMNI_COMENTARIOS')
 WHERE p.codigo = 'OMNI_OPERADOR'
   AND NOT EXISTS (SELECT 1 FROM perfis_permissoes x WHERE x.perfil_id = p.id AND x.permissao_id = pm.id);

COMMIT;
