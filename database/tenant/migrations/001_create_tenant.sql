--
-- PostgreSQL database dump
--

\restrict NIBIMLck5RIlimqrjEUrnqrsyJBo76ZoximTA6or2JeKtT1At3yKP1k4aZXn1Sh

-- Dumped from database version 18.4 (Debian 18.4-1.pgdg13+1)
-- Dumped by pg_dump version 18.4 (Debian 18.4-1.pgdg13+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- Name: fn_validar_faixa_avaliacao_numero(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_validar_faixa_avaliacao_numero() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_natureza VARCHAR(20);
    v_tipo_resposta VARCHAR(30);
BEGIN
    SELECT natureza, tipo_resposta
      INTO v_natureza, v_tipo_resposta
      FROM perguntas_diagnostico
     WHERE id = NEW.pergunta_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Pergunta % nÃ£o encontrada', NEW.pergunta_id;
    END IF;

    IF v_tipo_resposta <> 'NUMERO' THEN
        RAISE EXCEPTION
            'Faixa de avaliaÃ§Ã£o sÃ³ pode ser cadastrada para pergunta NUMERO';
    END IF;

    IF v_natureza <> 'AVALIATIVA' THEN
        RAISE EXCEPTION
            'Faixa de avaliaÃ§Ã£o sÃ³ pode ser cadastrada para pergunta NUMERO AVALIATIVA';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM faixas_avaliacao_numero f
        WHERE f.pergunta_id = NEW.pergunta_id
          AND f.id <> NEW.id
          AND COALESCE(f.valor_min, '-Infinity'::numeric)
              <= COALESCE(NEW.valor_max, 'Infinity'::numeric)
          AND COALESCE(NEW.valor_min, '-Infinity'::numeric)
              <= COALESCE(f.valor_max, 'Infinity'::numeric)
    ) THEN
        RAISE EXCEPTION
            'Faixa numÃ©rica sobrepÃµe outra faixa existente para esta pergunta';
    END IF;

    RETURN NEW;
END;
$$;


--
-- Name: fn_validar_opcao_pergunta_diagnostico(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_validar_opcao_pergunta_diagnostico() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_natureza VARCHAR(20);
    v_tipo_resposta VARCHAR(30);
BEGIN
    SELECT natureza, tipo_resposta
      INTO v_natureza, v_tipo_resposta
      FROM perguntas_diagnostico
     WHERE id = NEW.pergunta_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Pergunta % nÃ£o encontrada', NEW.pergunta_id;
    END IF;

    IF v_natureza = 'CONTEXTO' AND NEW.estado_interno IS NOT NULL THEN
        RAISE EXCEPTION 'Pergunta CONTEXTO nÃ£o aceita estado_interno';
    END IF;

    IF v_tipo_resposta IN ('NUMERO', 'TEXTO_CURTO') THEN
        RAISE EXCEPTION
            'Pergunta do tipo % nÃ£o utiliza opcoes_pergunta_diagnostico',
            v_tipo_resposta;
    END IF;

    RETURN NEW;
END;
$$;


--
-- Name: fn_validar_regra_exibicao_pergunta(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_validar_regra_exibicao_pergunta() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM opcoes_pergunta_diagnostico o
        WHERE o.id = NEW.opcao_origem_id
          AND o.pergunta_id = NEW.pergunta_origem_id
    ) THEN
        RAISE EXCEPTION
            'opcao_origem_id nÃ£o pertence Ã  pergunta_origem_id informada';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM formularios_perguntas fp
        WHERE fp.formulario_id = NEW.formulario_id
          AND fp.pergunta_id = NEW.pergunta_origem_id
          AND fp.ativo = true
    ) THEN
        RAISE EXCEPTION
            'Pergunta de origem nÃ£o estÃ¡ ativa no formulÃ¡rio informado';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM formularios_perguntas fp
        WHERE fp.formulario_id = NEW.formulario_id
          AND fp.pergunta_id = NEW.pergunta_destino_id
          AND fp.ativo = true
    ) THEN
        RAISE EXCEPTION
            'Pergunta de destino nÃ£o estÃ¡ ativa no formulÃ¡rio informado';
    END IF;

    RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: areas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.areas (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    empresa_id uuid NOT NULL,
    unidade_id uuid,
    codigo character varying(50) NOT NULL,
    nome character varying(150) NOT NULL,
    descricao text,
    ativo boolean DEFAULT true NOT NULL,
    ordem integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT areas_ordem_check CHECK ((ordem > 0))
);


--
-- Name: categorias_diagnostico; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.categorias_diagnostico (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    empresa_id uuid,
    nome character varying(120) NOT NULL,
    descricao text,
    ordem integer DEFAULT 0 NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: contatos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.contatos (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    empresa_id uuid NOT NULL,
    nome character varying(150) NOT NULL,
    email character varying(150),
    telefone character varying(30),
    empresa_contato character varying(150),
    mensagem text,
    origem character varying(50) DEFAULT 'site'::character varying NOT NULL,
    status character varying(30) DEFAULT 'novo'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    tipo_solicitacao character varying(30) DEFAULT 'CONTATO'::character varying NOT NULL,
    cnpj character varying(20),
    cidade character varying(120),
    uf character varying(2),
    site_instagram character varying(255),
    segmento character varying(150),
    objetivos text[],
    consentimento_dados boolean DEFAULT false NOT NULL,
    consentimento_em timestamp with time zone,
    consentimento_versao character varying(30),
    chatwoot_contact_id bigint,
    origem_primeiro_contato character varying(50),
    origem_ultimo_contato character varying(50),
    origem_contato_id uuid,
    CONSTRAINT ck_contatos_tipo_solicitacao CHECK (((tipo_solicitacao)::text = ANY (ARRAY[('CONTATO'::character varying)::text, ('DIAGNOSTICO'::character varying)::text])))
);


--
-- Name: COLUMN contatos.mensagem; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.contatos.mensagem IS 'LEGADO/COMPATIBILIDADE: mensagem original do formulario. Novas interacoes relevantes devem ser registradas em interacoes.';


--
-- Name: COLUMN contatos.chatwoot_contact_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.contatos.chatwoot_contact_id IS 'ID do contato correspondente no Chatwoot. Usado para deduplicacao e sincronizacao apos qualificacao do contato.';


--
-- Name: COLUMN contatos.origem_primeiro_contato; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.contatos.origem_primeiro_contato IS 'Canal/origem em que o contato entrou pela primeira vez na base oficial da MDP.';


--
-- Name: COLUMN contatos.origem_ultimo_contato; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.contatos.origem_ultimo_contato IS 'Canal/origem mais recente conhecido para o contato na base oficial da MDP.';


--
-- Name: diagnosticos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.diagnosticos (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    empresa_id uuid NOT NULL,
    nome_contato character varying(150),
    email_contato character varying(150),
    telefone_contato character varying(30),
    empresa_avaliada character varying(150),
    status character varying(30) DEFAULT 'em_andamento'::character varying NOT NULL,
    pontuacao_total numeric(10,2),
    classificacao character varying(50),
    iniciado_em timestamp with time zone DEFAULT now() NOT NULL,
    concluido_em timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    contato_id uuid,
    formulario_id uuid,
    token_hash text,
    token_expira_em timestamp with time zone,
    token_revogado_em timestamp with time zone
);


--
-- Name: COLUMN diagnosticos.contato_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.diagnosticos.contato_id IS 'Contato oficial da MDP associado ao diagnostico. Nome/e-mail/telefone existentes podem continuar como snapshot historico.';


--
-- Name: COLUMN diagnosticos.formulario_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.diagnosticos.formulario_id IS 'Formulario de diagnostico utilizado nesta execucao.';


--
-- Name: COLUMN diagnosticos.token_hash; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.diagnosticos.token_hash IS 'Hash do token pÃºblico de acesso Ã  instÃ¢ncia do diagnÃ³stico. O token puro nÃ£o deve ser persistido.';


--
-- Name: COLUMN diagnosticos.token_expira_em; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.diagnosticos.token_expira_em IS 'Data/hora limite para uso do token pÃºblico da instÃ¢ncia. NULL significa sem expiraÃ§Ã£o definida.';


--
-- Name: COLUMN diagnosticos.token_revogado_em; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.diagnosticos.token_revogado_em IS 'Data/hora de revogaÃ§Ã£o do token pÃºblico. NULL significa token nÃ£o revogado.';


--
-- Name: empresas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.empresas (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    nome character varying(150) NOT NULL,
    slug character varying(80) NOT NULL,
    cnpj character varying(20),
    email character varying(150),
    telefone character varying(30),
    dominio character varying(255),
    ativo boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    status character varying(30) DEFAULT 'EM_AVALIACAO'::character varying NOT NULL,
    tenant_id uuid,
    CONSTRAINT ck_empresas_status CHECK (((status)::text = ANY (ARRAY[('EM_AVALIACAO'::character varying)::text, ('CLIENTE'::character varying)::text, ('DESCARTADA'::character varying)::text])))
);


--
-- Name: COLUMN empresas.status; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.empresas.status IS 'SituaÃ§Ã£o comercial/relacional da empresa: EM_AVALIACAO, CLIENTE ou DESCARTADA. Independente do status de diagnosticos.';


--
-- Name: COLUMN empresas.tenant_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.empresas.tenant_id IS 'Tenant proprietÃ¡rio da empresa/organizaÃ§Ã£o. Nullable durante a transiÃ§Ã£o do modelo legado.';


--
-- Name: evidencias_diagnostico; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.evidencias_diagnostico (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    empresa_id uuid NOT NULL,
    diagnostico_id uuid NOT NULL,
    resposta_id uuid,
    tipo character varying(50) NOT NULL,
    arquivo_url text,
    descricao text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE evidencias_diagnostico; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.evidencias_diagnostico IS 'Armazena evidencias associadas a um diagnostico e opcionalmente a uma resposta especifica.';


--
-- Name: faixas_avaliacao_numero; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.faixas_avaliacao_numero (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    pergunta_id uuid NOT NULL,
    valor_min numeric(15,4),
    valor_max numeric(15,4),
    estado_interno character varying(20) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_faixas_avaliacao_numero_estado CHECK (((estado_interno)::text = ANY (ARRAY[('ALTO'::character varying)::text, ('MEDIO'::character varying)::text, ('BAIXO'::character varying)::text, ('NA'::character varying)::text, ('NAO_SEI'::character varying)::text]))),
    CONSTRAINT ck_faixas_avaliacao_numero_limites CHECK (((valor_min IS NULL) OR (valor_max IS NULL) OR (valor_min <= valor_max)))
);


--
-- Name: formularios_diagnostico; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.formularios_diagnostico (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    empresa_id uuid,
    codigo character varying(50) NOT NULL,
    nome character varying(150) NOT NULL,
    descricao text,
    tipo character varying(50) NOT NULL,
    versao integer DEFAULT 1 NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_formularios_diagnostico_versao CHECK ((versao > 0))
);


--
-- Name: TABLE formularios_diagnostico; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.formularios_diagnostico IS 'Define modelos versionados de diagnostico, como Basico, Avancado ou especializados.';


--
-- Name: formularios_perguntas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.formularios_perguntas (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    formulario_id uuid NOT NULL,
    pergunta_id uuid NOT NULL,
    ordem integer DEFAULT 0 NOT NULL,
    obrigatoria boolean DEFAULT false NOT NULL,
    peso numeric DEFAULT 1 NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_formularios_perguntas_peso CHECK ((peso >= (0)::numeric))
);


--
-- Name: TABLE formularios_perguntas; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.formularios_perguntas IS 'Relaciona perguntas do catalogo aos formularios, permitindo ordem, peso e obrigatoriedade especificos.';


--
-- Name: interacoes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.interacoes (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    empresa_id uuid NOT NULL,
    contato_id uuid NOT NULL,
    canal character varying(30) NOT NULL,
    origem character varying(50),
    tipo_interacao character varying(30) DEFAULT 'MENSAGEM'::character varying NOT NULL,
    mensagem text,
    direcao character varying(15),
    classificacao character varying(30),
    chatwoot_conversation_id bigint,
    chatwoot_message_id bigint,
    chatwoot_inbox_id bigint,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    tipo_interacao_id uuid
);


--
-- Name: TABLE interacoes; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.interacoes IS 'Registra interacoes relevantes de contatos qualificados da MDP. O Chatwoot continua sendo a caixa operacional que pode conter spam, testes, trotes e mensagens nao qualificadas.';


--
-- Name: COLUMN interacoes.canal; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.interacoes.canal IS 'Canal da interacao, por exemplo SITE, EMAIL, WHATSAPP ou INSTAGRAM.';


--
-- Name: COLUMN interacoes.classificacao; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.interacoes.classificacao IS 'Classificacao funcional da interacao, por exemplo CONTATO, DIAGNOSTICO, FORNECEDOR ou outra definida pela aplicacao.';


--
-- Name: COLUMN interacoes.chatwoot_message_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.interacoes.chatwoot_message_id IS 'ID da mensagem no Chatwoot. Quando informado, o indice unico evita processamento duplicado pelo n8n/API.';


--
-- Name: opcoes_pergunta_diagnostico; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.opcoes_pergunta_diagnostico (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    pergunta_id uuid NOT NULL,
    valor character varying(80) NOT NULL,
    rotulo character varying(150) NOT NULL,
    pontuacao numeric(10,2) DEFAULT 0 NOT NULL,
    ordem integer DEFAULT 0 NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    estado_interno character varying(20),
    CONSTRAINT ck_opcoes_pergunta_estado_interno CHECK (((estado_interno IS NULL) OR ((estado_interno)::text = ANY (ARRAY[('ALTO'::character varying)::text, ('MEDIO'::character varying)::text, ('BAIXO'::character varying)::text, ('NA'::character varying)::text, ('NAO_SEI'::character varying)::text]))))
);


--
-- Name: origens_contato; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.origens_contato (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    empresa_id uuid,
    codigo character varying(50) NOT NULL,
    nome character varying(120) NOT NULL,
    descricao text,
    ativo boolean DEFAULT true NOT NULL,
    ordem integer NOT NULL,
    padrao_sistema boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: perfis; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.perfis (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    codigo character varying(40) NOT NULL,
    nome character varying(80) NOT NULL,
    descricao text,
    ativo boolean DEFAULT true NOT NULL,
    acesso_total boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: perfis_permissoes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.perfis_permissoes (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    perfil_id uuid NOT NULL,
    permissao_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: perguntas_diagnostico; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.perguntas_diagnostico (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    empresa_id uuid,
    categoria_id uuid NOT NULL,
    pergunta text NOT NULL,
    tipo_resposta character varying(30) NOT NULL,
    peso numeric(10,2) DEFAULT 1 NOT NULL,
    ordem integer DEFAULT 0 NOT NULL,
    obrigatoria boolean DEFAULT false NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    codigo character varying(30),
    metodo_avaliacao character varying(20) DEFAULT 'cliente'::character varying NOT NULL,
    ajuda text,
    gera_achado boolean DEFAULT true NOT NULL,
    natureza character varying(20) DEFAULT 'CONTEXTO'::character varying NOT NULL,
    ideal text,
    sugestao text,
    CONSTRAINT ck_perguntas_diagnostico_natureza CHECK (((natureza)::text = ANY (ARRAY[('AVALIATIVA'::character varying)::text, ('CONTEXTO'::character varying)::text]))),
    CONSTRAINT ck_perguntas_diagnostico_tipo_natureza CHECK ((NOT (((tipo_resposta)::text = ANY (ARRAY[('MULTIPLA_ESCOLHA'::character varying)::text, ('TEXTO_CURTO'::character varying)::text])) AND ((natureza)::text <> 'CONTEXTO'::text)))),
    CONSTRAINT ck_perguntas_diagnostico_tipo_resposta CHECK (((tipo_resposta)::text = ANY (ARRAY[('ESCOLHA_UNICA'::character varying)::text, ('MULTIPLA_ESCOLHA'::character varying)::text, ('NUMERO'::character varying)::text, ('TEXTO_CURTO'::character varying)::text])))
);


--
-- Name: permissoes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.permissoes (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    codigo character varying(100) NOT NULL,
    nome character varying(150) NOT NULL,
    descricao text,
    ativo boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: regras_exibicao_perguntas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.regras_exibicao_perguntas (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    formulario_id uuid NOT NULL,
    pergunta_origem_id uuid NOT NULL,
    opcao_origem_id uuid NOT NULL,
    pergunta_destino_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_regras_exibicao_perguntas_distintas CHECK ((pergunta_origem_id <> pergunta_destino_id))
);


--
-- Name: respostas_diagnostico; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.respostas_diagnostico (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    diagnostico_id uuid NOT NULL,
    pergunta_id uuid NOT NULL,
    resposta_texto text,
    resposta_numero numeric(15,4),
    resposta_boolean boolean,
    pontuacao numeric(10,2),
    observacao text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    opcao_id uuid,
    estado_interno character varying(20),
    CONSTRAINT ck_respostas_diagnostico_estado_interno CHECK (((estado_interno IS NULL) OR ((estado_interno)::text = ANY (ARRAY[('ALTO'::character varying)::text, ('MEDIO'::character varying)::text, ('BAIXO'::character varying)::text, ('NA'::character varying)::text, ('NAO_SEI'::character varying)::text]))))
);


--
-- Name: respostas_diagnostico_opcoes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.respostas_diagnostico_opcoes (
    resposta_id uuid NOT NULL,
    opcao_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: sessoes_usuario; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sessoes_usuario (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    usuario_id uuid NOT NULL,
    empresa_id uuid,
    refresh_token_hash text NOT NULL,
    criada_em timestamp with time zone DEFAULT now() NOT NULL,
    expira_em timestamp with time zone NOT NULL,
    ultimo_uso_em timestamp with time zone,
    revogada_em timestamp with time zone,
    motivo_revogacao character varying(255),
    ip_origem inet,
    user_agent text,
    CONSTRAINT sessoes_usuario_expiracao_check CHECK ((expira_em > criada_em))
);


--
-- Name: tenants; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tenants (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    codigo character varying(50) NOT NULL,
    nome character varying(150) NOT NULL,
    slug character varying(80) NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE tenants; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.tenants IS 'Fronteira lÃ³gica de isolamento multi-tenant da plataforma MDP. Tenant nÃ£o Ã© sinÃ´nimo de empresa/organizaÃ§Ã£o.';


--
-- Name: COLUMN tenants.codigo; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.tenants.codigo IS 'CÃ³digo estÃ¡vel interno do tenant.';


--
-- Name: COLUMN tenants.slug; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.tenants.slug IS 'Identificador textual do tenant para uso em contexto, configuraÃ§Ã£o e URLs quando aplicÃ¡vel.';


--
-- Name: tipos_interacao; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tipos_interacao (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    empresa_id uuid,
    codigo character varying(50) NOT NULL,
    nome character varying(120) NOT NULL,
    descricao text,
    ativo boolean DEFAULT true NOT NULL,
    ordem integer NOT NULL,
    padrao_sistema boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: tipos_unidade; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tipos_unidade (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    empresa_id uuid,
    codigo character varying(50) NOT NULL,
    nome character varying(120) NOT NULL,
    descricao text,
    ativo boolean DEFAULT true NOT NULL,
    ordem integer NOT NULL,
    padrao_sistema boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT tipos_unidade_ordem_check CHECK ((ordem > 0)),
    CONSTRAINT tipos_unidade_padrao_check CHECK (((NOT padrao_sistema) OR (empresa_id IS NULL)))
);


--
-- Name: unidades_empresa; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.unidades_empresa (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    empresa_id uuid NOT NULL,
    tipo_unidade_id uuid NOT NULL,
    codigo character varying(50) NOT NULL,
    nome character varying(150) NOT NULL,
    nome_fantasia character varying(150),
    cnpj character varying(20),
    email character varying(150),
    telefone character varying(30),
    cep character varying(10),
    logradouro character varying(180),
    numero character varying(30),
    complemento character varying(100),
    bairro character varying(100),
    cidade character varying(120),
    uf character varying(2),
    ativo boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: usuarios; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuarios_tenant (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    platform_usuario_id uuid NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: usuarios_areas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuarios_areas (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    usuario_empresa_id uuid NOT NULL,
    area_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: usuarios_empresas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuarios_empresas (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    usuario_id uuid NOT NULL,
    empresa_id uuid NOT NULL,
    perfil_id uuid NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    acesso_todas_unidades boolean DEFAULT false NOT NULL,
    acesso_todas_areas boolean DEFAULT false NOT NULL
);


--
-- Name: usuarios_tenants; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuarios_tenants (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    usuario_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    perfil_id uuid NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE usuarios_tenants; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.usuarios_tenants IS 'Vincula usuÃ¡rios aos tenants da plataforma e define o perfil do usuÃ¡rio dentro de cada tenant.';


--
-- Name: usuarios_unidades; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuarios_unidades (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    usuario_empresa_id uuid NOT NULL,
    unidade_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: areas areas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.areas
    ADD CONSTRAINT areas_pkey PRIMARY KEY (id);


--
-- Name: categorias_diagnostico categorias_diagnostico_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categorias_diagnostico
    ADD CONSTRAINT categorias_diagnostico_pkey PRIMARY KEY (id);


--
-- Name: contatos contatos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contatos
    ADD CONSTRAINT contatos_pkey PRIMARY KEY (id);


--
-- Name: diagnosticos diagnosticos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.diagnosticos
    ADD CONSTRAINT diagnosticos_pkey PRIMARY KEY (id);


--
-- Name: empresas empresas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.empresas
    ADD CONSTRAINT empresas_pkey PRIMARY KEY (id);


--
-- Name: empresas empresas_slug_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.empresas
    ADD CONSTRAINT empresas_slug_key UNIQUE (slug);


--
-- Name: evidencias_diagnostico evidencias_diagnostico_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidencias_diagnostico
    ADD CONSTRAINT evidencias_diagnostico_pkey PRIMARY KEY (id);


--
-- Name: faixas_avaliacao_numero faixas_avaliacao_numero_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.faixas_avaliacao_numero
    ADD CONSTRAINT faixas_avaliacao_numero_pkey PRIMARY KEY (id);


--
-- Name: formularios_diagnostico formularios_diagnostico_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.formularios_diagnostico
    ADD CONSTRAINT formularios_diagnostico_pkey PRIMARY KEY (id);


--
-- Name: formularios_perguntas formularios_perguntas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.formularios_perguntas
    ADD CONSTRAINT formularios_perguntas_pkey PRIMARY KEY (id);


--
-- Name: interacoes interacoes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interacoes
    ADD CONSTRAINT interacoes_pkey PRIMARY KEY (id);


--
-- Name: opcoes_pergunta_diagnostico opcoes_pergunta_diagnostico_pergunta_id_valor_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.opcoes_pergunta_diagnostico
    ADD CONSTRAINT opcoes_pergunta_diagnostico_pergunta_id_valor_key UNIQUE (pergunta_id, valor);


--
-- Name: opcoes_pergunta_diagnostico opcoes_pergunta_diagnostico_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.opcoes_pergunta_diagnostico
    ADD CONSTRAINT opcoes_pergunta_diagnostico_pkey PRIMARY KEY (id);


--
-- Name: origens_contato origens_contato_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.origens_contato
    ADD CONSTRAINT origens_contato_pkey PRIMARY KEY (id);


--
-- Name: perfis perfis_codigo_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.perfis
    ADD CONSTRAINT perfis_codigo_key UNIQUE (codigo);


--
-- Name: perfis_permissoes perfis_permissoes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.perfis_permissoes
    ADD CONSTRAINT perfis_permissoes_pkey PRIMARY KEY (id);


--
-- Name: perfis_permissoes perfis_permissoes_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.perfis_permissoes
    ADD CONSTRAINT perfis_permissoes_unique UNIQUE (perfil_id, permissao_id);


--
-- Name: perfis perfis_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.perfis
    ADD CONSTRAINT perfis_pkey PRIMARY KEY (id);


--
-- Name: perguntas_diagnostico perguntas_diagnostico_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.perguntas_diagnostico
    ADD CONSTRAINT perguntas_diagnostico_pkey PRIMARY KEY (id);


--
-- Name: permissoes permissoes_codigo_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.permissoes
    ADD CONSTRAINT permissoes_codigo_key UNIQUE (codigo);


--
-- Name: permissoes permissoes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.permissoes
    ADD CONSTRAINT permissoes_pkey PRIMARY KEY (id);


--
-- Name: respostas_diagnostico_opcoes pk_respostas_diagnostico_opcoes; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.respostas_diagnostico_opcoes
    ADD CONSTRAINT pk_respostas_diagnostico_opcoes PRIMARY KEY (resposta_id, opcao_id);


--
-- Name: regras_exibicao_perguntas regras_exibicao_perguntas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.regras_exibicao_perguntas
    ADD CONSTRAINT regras_exibicao_perguntas_pkey PRIMARY KEY (id);


--
-- Name: respostas_diagnostico respostas_diagnostico_diagnostico_id_pergunta_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.respostas_diagnostico
    ADD CONSTRAINT respostas_diagnostico_diagnostico_id_pergunta_id_key UNIQUE (diagnostico_id, pergunta_id);


--
-- Name: respostas_diagnostico respostas_diagnostico_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.respostas_diagnostico
    ADD CONSTRAINT respostas_diagnostico_pkey PRIMARY KEY (id);


--
-- Name: sessoes_usuario sessoes_usuario_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sessoes_usuario
    ADD CONSTRAINT sessoes_usuario_pkey PRIMARY KEY (id);


--
-- Name: tenants tenants_codigo_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT tenants_codigo_key UNIQUE (codigo);


--
-- Name: tenants tenants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT tenants_pkey PRIMARY KEY (id);


--
-- Name: tenants tenants_slug_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT tenants_slug_key UNIQUE (slug);


--
-- Name: tipos_interacao tipos_interacao_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tipos_interacao
    ADD CONSTRAINT tipos_interacao_pkey PRIMARY KEY (id);


--
-- Name: tipos_unidade tipos_unidade_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tipos_unidade
    ADD CONSTRAINT tipos_unidade_pkey PRIMARY KEY (id);


--
-- Name: unidades_empresa unidades_empresa_codigo_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unidades_empresa
    ADD CONSTRAINT unidades_empresa_codigo_key UNIQUE (empresa_id, codigo);


--
-- Name: unidades_empresa unidades_empresa_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unidades_empresa
    ADD CONSTRAINT unidades_empresa_pkey PRIMARY KEY (id);


--
-- Name: formularios_diagnostico uq_formularios_diagnostico_empresa_codigo_versao; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.formularios_diagnostico
    ADD CONSTRAINT uq_formularios_diagnostico_empresa_codigo_versao UNIQUE (empresa_id, codigo, versao);


--
-- Name: formularios_perguntas uq_formularios_perguntas; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.formularios_perguntas
    ADD CONSTRAINT uq_formularios_perguntas UNIQUE (formulario_id, pergunta_id);


--
-- Name: regras_exibicao_perguntas uq_regras_exibicao_perguntas; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.regras_exibicao_perguntas
    ADD CONSTRAINT uq_regras_exibicao_perguntas UNIQUE (formulario_id, pergunta_origem_id, opcao_origem_id, pergunta_destino_id);


--
-- Name: usuarios_areas usuarios_areas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios_areas
    ADD CONSTRAINT usuarios_areas_pkey PRIMARY KEY (id);


--
-- Name: usuarios_areas usuarios_areas_vinculo_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios_areas
    ADD CONSTRAINT usuarios_areas_vinculo_key UNIQUE (usuario_empresa_id, area_id);


--
-- Name: usuarios usuarios_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_email_key UNIQUE (email);


--
-- Name: usuarios_empresas usuarios_empresas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios_empresas
    ADD CONSTRAINT usuarios_empresas_pkey PRIMARY KEY (id);


--
-- Name: usuarios_empresas usuarios_empresas_usuario_id_empresa_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios_empresas
    ADD CONSTRAINT usuarios_empresas_usuario_id_empresa_id_key UNIQUE (usuario_id, empresa_id);


--
-- Name: usuarios usuarios_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_pkey PRIMARY KEY (id);


--
-- Name: usuarios_tenants usuarios_tenants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios_tenants
    ADD CONSTRAINT usuarios_tenants_pkey PRIMARY KEY (id);


--
-- Name: usuarios_tenants usuarios_tenants_usuario_tenant_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios_tenants
    ADD CONSTRAINT usuarios_tenants_usuario_tenant_key UNIQUE (usuario_id, tenant_id);


--
-- Name: usuarios_unidades usuarios_unidades_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios_unidades
    ADD CONSTRAINT usuarios_unidades_pkey PRIMARY KEY (id);


--
-- Name: usuarios_unidades usuarios_unidades_vinculo_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios_unidades
    ADD CONSTRAINT usuarios_unidades_vinculo_key UNIQUE (usuario_empresa_id, unidade_id);


--
-- Name: idx_categorias_empresa; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_categorias_empresa ON public.categorias_diagnostico USING btree (empresa_id);


--
-- Name: idx_contatos_empresa_email_normalizado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_contatos_empresa_email_normalizado ON public.contatos USING btree (empresa_id, lower((email)::text)) WHERE (email IS NOT NULL);


--
-- Name: idx_contatos_empresa_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_contatos_empresa_id ON public.contatos USING btree (empresa_id);


--
-- Name: idx_contatos_empresa_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_contatos_empresa_status ON public.contatos USING btree (empresa_id, status);


--
-- Name: idx_contatos_origem_contato; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_contatos_origem_contato ON public.contatos USING btree (origem_contato_id);


--
-- Name: idx_contatos_tipo_solicitacao; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_contatos_tipo_solicitacao ON public.contatos USING btree (empresa_id, tipo_solicitacao);


--
-- Name: idx_diagnosticos_contato; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_diagnosticos_contato ON public.diagnosticos USING btree (contato_id) WHERE (contato_id IS NOT NULL);


--
-- Name: idx_diagnosticos_empresa; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_diagnosticos_empresa ON public.diagnosticos USING btree (empresa_id);


--
-- Name: idx_diagnosticos_formulario_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_diagnosticos_formulario_id ON public.diagnosticos USING btree (formulario_id);


--
-- Name: idx_diagnosticos_token_expira_em; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_diagnosticos_token_expira_em ON public.diagnosticos USING btree (token_expira_em) WHERE (token_expira_em IS NOT NULL);


--
-- Name: idx_empresas_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_empresas_status ON public.empresas USING btree (status);


--
-- Name: idx_evidencias_diagnostico_diagnostico_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_evidencias_diagnostico_diagnostico_id ON public.evidencias_diagnostico USING btree (diagnostico_id);


--
-- Name: idx_evidencias_diagnostico_empresa_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_evidencias_diagnostico_empresa_id ON public.evidencias_diagnostico USING btree (empresa_id);


--
-- Name: idx_evidencias_diagnostico_resposta_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_evidencias_diagnostico_resposta_id ON public.evidencias_diagnostico USING btree (resposta_id);


--
-- Name: idx_evidencias_diagnostico_tipo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_evidencias_diagnostico_tipo ON public.evidencias_diagnostico USING btree (tipo);


--
-- Name: idx_formularios_diagnostico_ativo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_formularios_diagnostico_ativo ON public.formularios_diagnostico USING btree (ativo);


--
-- Name: idx_formularios_diagnostico_empresa_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_formularios_diagnostico_empresa_id ON public.formularios_diagnostico USING btree (empresa_id);


--
-- Name: idx_formularios_diagnostico_tipo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_formularios_diagnostico_tipo ON public.formularios_diagnostico USING btree (tipo);


--
-- Name: idx_formularios_perguntas_formulario_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_formularios_perguntas_formulario_id ON public.formularios_perguntas USING btree (formulario_id);


--
-- Name: idx_formularios_perguntas_ordem; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_formularios_perguntas_ordem ON public.formularios_perguntas USING btree (formulario_id, ordem);


--
-- Name: idx_formularios_perguntas_pergunta_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_formularios_perguntas_pergunta_id ON public.formularios_perguntas USING btree (pergunta_id);


--
-- Name: idx_interacoes_chatwoot_conversation; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_interacoes_chatwoot_conversation ON public.interacoes USING btree (empresa_id, chatwoot_conversation_id) WHERE (chatwoot_conversation_id IS NOT NULL);


--
-- Name: idx_interacoes_contato_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_interacoes_contato_created ON public.interacoes USING btree (contato_id, created_at DESC);


--
-- Name: idx_interacoes_empresa_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_interacoes_empresa_created ON public.interacoes USING btree (empresa_id, created_at DESC);


--
-- Name: idx_interacoes_tipo_interacao; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_interacoes_tipo_interacao ON public.interacoes USING btree (tipo_interacao_id);


--
-- Name: idx_opcoes_pergunta; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_opcoes_pergunta ON public.opcoes_pergunta_diagnostico USING btree (pergunta_id);


--
-- Name: idx_origens_contato_empresa; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_origens_contato_empresa ON public.origens_contato USING btree (empresa_id);


--
-- Name: idx_perfis_permissoes_perfil; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_perfis_permissoes_perfil ON public.perfis_permissoes USING btree (perfil_id);


--
-- Name: idx_perfis_permissoes_permissao; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_perfis_permissoes_permissao ON public.perfis_permissoes USING btree (permissao_id);


--
-- Name: idx_perguntas_categoria; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_perguntas_categoria ON public.perguntas_diagnostico USING btree (categoria_id);


--
-- Name: idx_perguntas_empresa; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_perguntas_empresa ON public.perguntas_diagnostico USING btree (empresa_id);


--
-- Name: idx_respostas_diagnostico; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_respostas_diagnostico ON public.respostas_diagnostico USING btree (diagnostico_id);


--
-- Name: idx_sessoes_usuario_empresa; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_sessoes_usuario_empresa ON public.sessoes_usuario USING btree (empresa_id);


--
-- Name: idx_sessoes_usuario_expira; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_sessoes_usuario_expira ON public.sessoes_usuario USING btree (expira_em);


--
-- Name: idx_sessoes_usuario_revogada; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_sessoes_usuario_revogada ON public.sessoes_usuario USING btree (revogada_em);


--
-- Name: idx_sessoes_usuario_usuario; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_sessoes_usuario_usuario ON public.sessoes_usuario USING btree (usuario_id);


--
-- Name: idx_tipos_interacao_empresa; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tipos_interacao_empresa ON public.tipos_interacao USING btree (empresa_id);


--
-- Name: idx_usuarios_empresas_empresa; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_usuarios_empresas_empresa ON public.usuarios_empresas USING btree (empresa_id);


--
-- Name: idx_usuarios_empresas_usuario; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_usuarios_empresas_usuario ON public.usuarios_empresas USING btree (usuario_id);


--
-- Name: ix_areas_empresa_ativo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_areas_empresa_ativo ON public.areas USING btree (empresa_id, ativo);


--
-- Name: ix_areas_unidade_ativo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_areas_unidade_ativo ON public.areas USING btree (unidade_id, ativo);


--
-- Name: ix_empresas_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_empresas_tenant ON public.empresas USING btree (tenant_id);


--
-- Name: ix_faixas_avaliacao_numero_pergunta; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_faixas_avaliacao_numero_pergunta ON public.faixas_avaliacao_numero USING btree (pergunta_id);


--
-- Name: ix_regras_exibicao_destino; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_regras_exibicao_destino ON public.regras_exibicao_perguntas USING btree (pergunta_destino_id);


--
-- Name: ix_regras_exibicao_formulario; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_regras_exibicao_formulario ON public.regras_exibicao_perguntas USING btree (formulario_id);


--
-- Name: ix_regras_exibicao_origem; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_regras_exibicao_origem ON public.regras_exibicao_perguntas USING btree (pergunta_origem_id, opcao_origem_id);


--
-- Name: ix_respostas_diagnostico_estado_interno; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_respostas_diagnostico_estado_interno ON public.respostas_diagnostico USING btree (estado_interno);


--
-- Name: ix_respostas_diagnostico_opcao_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_respostas_diagnostico_opcao_id ON public.respostas_diagnostico USING btree (opcao_id);


--
-- Name: ix_respostas_diagnostico_opcoes_opcao; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_respostas_diagnostico_opcoes_opcao ON public.respostas_diagnostico_opcoes USING btree (opcao_id);


--
-- Name: ix_tipos_unidade_empresa_ativo_ordem; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tipos_unidade_empresa_ativo_ordem ON public.tipos_unidade USING btree (empresa_id, ativo, ordem);


--
-- Name: ix_unidades_empresa_empresa_ativo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_unidades_empresa_empresa_ativo ON public.unidades_empresa USING btree (empresa_id, ativo);


--
-- Name: ix_unidades_empresa_localidade; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_unidades_empresa_localidade ON public.unidades_empresa USING btree (cidade, uf);


--
-- Name: ix_unidades_empresa_tipo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_unidades_empresa_tipo ON public.unidades_empresa USING btree (tipo_unidade_id);


--
-- Name: ix_usuarios_areas_area; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_usuarios_areas_area ON public.usuarios_areas USING btree (area_id);


--
-- Name: ix_usuarios_tenants_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_usuarios_tenants_tenant ON public.usuarios_tenants USING btree (tenant_id);


--
-- Name: ix_usuarios_tenants_tenant_ativo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_usuarios_tenants_tenant_ativo ON public.usuarios_tenants USING btree (tenant_id, ativo);


--
-- Name: ix_usuarios_tenants_usuario; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_usuarios_tenants_usuario ON public.usuarios_tenants USING btree (usuario_id);


--
-- Name: ix_usuarios_unidades_unidade; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_usuarios_unidades_unidade ON public.usuarios_unidades USING btree (unidade_id);


--
-- Name: uq_contatos_empresa_chatwoot_contact; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_contatos_empresa_chatwoot_contact ON public.contatos USING btree (empresa_id, chatwoot_contact_id) WHERE (chatwoot_contact_id IS NOT NULL);


--
-- Name: uq_diagnosticos_token_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_diagnosticos_token_hash ON public.diagnosticos USING btree (token_hash) WHERE (token_hash IS NOT NULL);


--
-- Name: uq_faixas_avaliacao_numero_pergunta_estado; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_faixas_avaliacao_numero_pergunta_estado ON public.faixas_avaliacao_numero USING btree (pergunta_id, estado_interno);


--
-- Name: uq_interacoes_empresa_chatwoot_message; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_interacoes_empresa_chatwoot_message ON public.interacoes USING btree (empresa_id, chatwoot_message_id) WHERE (chatwoot_message_id IS NOT NULL);


--
-- Name: uq_opcoes_pergunta_estado_interno; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_opcoes_pergunta_estado_interno ON public.opcoes_pergunta_diagnostico USING btree (pergunta_id, estado_interno) WHERE (estado_interno IS NOT NULL);


--
-- Name: uq_origens_contato_empresa_codigo; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_origens_contato_empresa_codigo ON public.origens_contato USING btree (empresa_id, upper((codigo)::text)) WHERE (empresa_id IS NOT NULL);


--
-- Name: uq_origens_contato_global_codigo; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_origens_contato_global_codigo ON public.origens_contato USING btree (upper((codigo)::text)) WHERE (empresa_id IS NULL);


--
-- Name: uq_perguntas_codigo_global; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_perguntas_codigo_global ON public.perguntas_diagnostico USING btree (codigo) WHERE ((codigo IS NOT NULL) AND (empresa_id IS NULL));


--
-- Name: uq_tipos_interacao_empresa_codigo; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_tipos_interacao_empresa_codigo ON public.tipos_interacao USING btree (empresa_id, upper((codigo)::text)) WHERE (empresa_id IS NOT NULL);


--
-- Name: uq_tipos_interacao_global_codigo; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_tipos_interacao_global_codigo ON public.tipos_interacao USING btree (upper((codigo)::text)) WHERE (empresa_id IS NULL);


--
-- Name: ux_areas_codigo_empresa_direta; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_areas_codigo_empresa_direta ON public.areas USING btree (empresa_id, codigo) WHERE (unidade_id IS NULL);


--
-- Name: ux_areas_codigo_unidade; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_areas_codigo_unidade ON public.areas USING btree (unidade_id, codigo) WHERE (unidade_id IS NOT NULL);


--
-- Name: ux_areas_ordem_empresa_direta; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_areas_ordem_empresa_direta ON public.areas USING btree (empresa_id, ordem) WHERE (unidade_id IS NULL);


--
-- Name: ux_areas_ordem_unidade; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_areas_ordem_unidade ON public.areas USING btree (unidade_id, ordem) WHERE (unidade_id IS NOT NULL);


--
-- Name: ux_tipos_unidade_codigo_empresa; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_tipos_unidade_codigo_empresa ON public.tipos_unidade USING btree (empresa_id, codigo) WHERE (empresa_id IS NOT NULL);


--
-- Name: ux_tipos_unidade_codigo_global; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_tipos_unidade_codigo_global ON public.tipos_unidade USING btree (codigo) WHERE (empresa_id IS NULL);


--
-- Name: ux_unidades_empresa_cnpj_normalizado; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_unidades_empresa_cnpj_normalizado ON public.unidades_empresa USING btree (regexp_replace((cnpj)::text, '[^0-9]'::text, ''::text, 'g'::text)) WHERE ((cnpj IS NOT NULL) AND (btrim((cnpj)::text) <> ''::text));


--
-- Name: faixas_avaliacao_numero trg_validar_faixa_avaliacao_numero; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_validar_faixa_avaliacao_numero BEFORE INSERT OR UPDATE ON public.faixas_avaliacao_numero FOR EACH ROW EXECUTE FUNCTION public.fn_validar_faixa_avaliacao_numero();


--
-- Name: opcoes_pergunta_diagnostico trg_validar_opcao_pergunta_diagnostico; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_validar_opcao_pergunta_diagnostico BEFORE INSERT OR UPDATE ON public.opcoes_pergunta_diagnostico FOR EACH ROW EXECUTE FUNCTION public.fn_validar_opcao_pergunta_diagnostico();


--
-- Name: regras_exibicao_perguntas trg_validar_regra_exibicao_pergunta; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_validar_regra_exibicao_pergunta BEFORE INSERT OR UPDATE ON public.regras_exibicao_perguntas FOR EACH ROW EXECUTE FUNCTION public.fn_validar_regra_exibicao_pergunta();


--
-- Name: areas areas_empresa_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.areas
    ADD CONSTRAINT areas_empresa_id_fkey FOREIGN KEY (empresa_id) REFERENCES public.empresas(id) ON DELETE CASCADE;


--
-- Name: areas areas_unidade_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.areas
    ADD CONSTRAINT areas_unidade_id_fkey FOREIGN KEY (unidade_id) REFERENCES public.unidades_empresa(id) ON DELETE CASCADE;


--
-- Name: categorias_diagnostico categorias_diagnostico_empresa_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categorias_diagnostico
    ADD CONSTRAINT categorias_diagnostico_empresa_id_fkey FOREIGN KEY (empresa_id) REFERENCES public.empresas(id);


--
-- Name: contatos contatos_empresa_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contatos
    ADD CONSTRAINT contatos_empresa_id_fkey FOREIGN KEY (empresa_id) REFERENCES public.empresas(id);


--
-- Name: contatos contatos_origem_contato_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contatos
    ADD CONSTRAINT contatos_origem_contato_id_fkey FOREIGN KEY (origem_contato_id) REFERENCES public.origens_contato(id) ON DELETE RESTRICT;


--
-- Name: diagnosticos diagnosticos_empresa_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.diagnosticos
    ADD CONSTRAINT diagnosticos_empresa_id_fkey FOREIGN KEY (empresa_id) REFERENCES public.empresas(id);


--
-- Name: empresas empresas_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.empresas
    ADD CONSTRAINT empresas_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;


--
-- Name: diagnosticos fk_diagnosticos_contato; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.diagnosticos
    ADD CONSTRAINT fk_diagnosticos_contato FOREIGN KEY (contato_id) REFERENCES public.contatos(id);


--
-- Name: diagnosticos fk_diagnosticos_formulario; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.diagnosticos
    ADD CONSTRAINT fk_diagnosticos_formulario FOREIGN KEY (formulario_id) REFERENCES public.formularios_diagnostico(id);


--
-- Name: evidencias_diagnostico fk_evidencias_diagnostico_diagnostico; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidencias_diagnostico
    ADD CONSTRAINT fk_evidencias_diagnostico_diagnostico FOREIGN KEY (diagnostico_id) REFERENCES public.diagnosticos(id) ON DELETE CASCADE;


--
-- Name: evidencias_diagnostico fk_evidencias_diagnostico_empresa; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidencias_diagnostico
    ADD CONSTRAINT fk_evidencias_diagnostico_empresa FOREIGN KEY (empresa_id) REFERENCES public.empresas(id);


--
-- Name: evidencias_diagnostico fk_evidencias_diagnostico_resposta; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidencias_diagnostico
    ADD CONSTRAINT fk_evidencias_diagnostico_resposta FOREIGN KEY (resposta_id) REFERENCES public.respostas_diagnostico(id) ON DELETE SET NULL;


--
-- Name: faixas_avaliacao_numero fk_faixas_avaliacao_numero_pergunta; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.faixas_avaliacao_numero
    ADD CONSTRAINT fk_faixas_avaliacao_numero_pergunta FOREIGN KEY (pergunta_id) REFERENCES public.perguntas_diagnostico(id) ON DELETE CASCADE;


--
-- Name: formularios_diagnostico fk_formularios_diagnostico_empresa; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.formularios_diagnostico
    ADD CONSTRAINT fk_formularios_diagnostico_empresa FOREIGN KEY (empresa_id) REFERENCES public.empresas(id);


--
-- Name: formularios_perguntas fk_formularios_perguntas_formulario; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.formularios_perguntas
    ADD CONSTRAINT fk_formularios_perguntas_formulario FOREIGN KEY (formulario_id) REFERENCES public.formularios_diagnostico(id) ON DELETE CASCADE;


--
-- Name: formularios_perguntas fk_formularios_perguntas_pergunta; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.formularios_perguntas
    ADD CONSTRAINT fk_formularios_perguntas_pergunta FOREIGN KEY (pergunta_id) REFERENCES public.perguntas_diagnostico(id);


--
-- Name: interacoes fk_interacoes_contato; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interacoes
    ADD CONSTRAINT fk_interacoes_contato FOREIGN KEY (contato_id) REFERENCES public.contatos(id) ON DELETE CASCADE;


--
-- Name: interacoes fk_interacoes_empresa; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interacoes
    ADD CONSTRAINT fk_interacoes_empresa FOREIGN KEY (empresa_id) REFERENCES public.empresas(id);


--
-- Name: regras_exibicao_perguntas fk_regras_exibicao_formulario; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.regras_exibicao_perguntas
    ADD CONSTRAINT fk_regras_exibicao_formulario FOREIGN KEY (formulario_id) REFERENCES public.formularios_diagnostico(id) ON DELETE CASCADE;


--
-- Name: regras_exibicao_perguntas fk_regras_exibicao_opcao_origem; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.regras_exibicao_perguntas
    ADD CONSTRAINT fk_regras_exibicao_opcao_origem FOREIGN KEY (opcao_origem_id) REFERENCES public.opcoes_pergunta_diagnostico(id) ON DELETE CASCADE;


--
-- Name: regras_exibicao_perguntas fk_regras_exibicao_pergunta_destino; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.regras_exibicao_perguntas
    ADD CONSTRAINT fk_regras_exibicao_pergunta_destino FOREIGN KEY (pergunta_destino_id) REFERENCES public.perguntas_diagnostico(id) ON DELETE CASCADE;


--
-- Name: regras_exibicao_perguntas fk_regras_exibicao_pergunta_origem; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.regras_exibicao_perguntas
    ADD CONSTRAINT fk_regras_exibicao_pergunta_origem FOREIGN KEY (pergunta_origem_id) REFERENCES public.perguntas_diagnostico(id) ON DELETE CASCADE;


--
-- Name: respostas_diagnostico fk_respostas_diagnostico_opcao; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.respostas_diagnostico
    ADD CONSTRAINT fk_respostas_diagnostico_opcao FOREIGN KEY (opcao_id) REFERENCES public.opcoes_pergunta_diagnostico(id);


--
-- Name: respostas_diagnostico_opcoes fk_respostas_diagnostico_opcoes_opcao; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.respostas_diagnostico_opcoes
    ADD CONSTRAINT fk_respostas_diagnostico_opcoes_opcao FOREIGN KEY (opcao_id) REFERENCES public.opcoes_pergunta_diagnostico(id) ON DELETE CASCADE;


--
-- Name: respostas_diagnostico_opcoes fk_respostas_diagnostico_opcoes_resposta; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.respostas_diagnostico_opcoes
    ADD CONSTRAINT fk_respostas_diagnostico_opcoes_resposta FOREIGN KEY (resposta_id) REFERENCES public.respostas_diagnostico(id) ON DELETE CASCADE;


--
-- Name: interacoes interacoes_tipo_interacao_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interacoes
    ADD CONSTRAINT interacoes_tipo_interacao_id_fkey FOREIGN KEY (tipo_interacao_id) REFERENCES public.tipos_interacao(id) ON DELETE RESTRICT;


--
-- Name: opcoes_pergunta_diagnostico opcoes_pergunta_diagnostico_pergunta_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.opcoes_pergunta_diagnostico
    ADD CONSTRAINT opcoes_pergunta_diagnostico_pergunta_id_fkey FOREIGN KEY (pergunta_id) REFERENCES public.perguntas_diagnostico(id) ON DELETE CASCADE;


--
-- Name: origens_contato origens_contato_empresa_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.origens_contato
    ADD CONSTRAINT origens_contato_empresa_id_fkey FOREIGN KEY (empresa_id) REFERENCES public.empresas(id) ON DELETE CASCADE;


--
-- Name: perfis_permissoes perfis_permissoes_perfil_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.perfis_permissoes
    ADD CONSTRAINT perfis_permissoes_perfil_fkey FOREIGN KEY (perfil_id) REFERENCES public.perfis(id) ON DELETE CASCADE;


--
-- Name: perfis_permissoes perfis_permissoes_permissao_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.perfis_permissoes
    ADD CONSTRAINT perfis_permissoes_permissao_fkey FOREIGN KEY (permissao_id) REFERENCES public.permissoes(id) ON DELETE CASCADE;


--
-- Name: perguntas_diagnostico perguntas_diagnostico_categoria_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.perguntas_diagnostico
    ADD CONSTRAINT perguntas_diagnostico_categoria_id_fkey FOREIGN KEY (categoria_id) REFERENCES public.categorias_diagnostico(id);


--
-- Name: perguntas_diagnostico perguntas_diagnostico_empresa_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.perguntas_diagnostico
    ADD CONSTRAINT perguntas_diagnostico_empresa_id_fkey FOREIGN KEY (empresa_id) REFERENCES public.empresas(id);


--
-- Name: respostas_diagnostico respostas_diagnostico_diagnostico_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.respostas_diagnostico
    ADD CONSTRAINT respostas_diagnostico_diagnostico_id_fkey FOREIGN KEY (diagnostico_id) REFERENCES public.diagnosticos(id) ON DELETE CASCADE;


--
-- Name: respostas_diagnostico respostas_diagnostico_pergunta_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.respostas_diagnostico
    ADD CONSTRAINT respostas_diagnostico_pergunta_id_fkey FOREIGN KEY (pergunta_id) REFERENCES public.perguntas_diagnostico(id);


--
-- Name: sessoes_usuario sessoes_usuario_empresa_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sessoes_usuario
    ADD CONSTRAINT sessoes_usuario_empresa_fkey FOREIGN KEY (empresa_id) REFERENCES public.empresas(id) ON DELETE RESTRICT;


--
-- Name: sessoes_usuario sessoes_usuario_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sessoes_usuario
    ADD CONSTRAINT sessoes_usuario_usuario_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id) ON DELETE CASCADE;


--
-- Name: tipos_interacao tipos_interacao_empresa_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tipos_interacao
    ADD CONSTRAINT tipos_interacao_empresa_id_fkey FOREIGN KEY (empresa_id) REFERENCES public.empresas(id) ON DELETE CASCADE;


--
-- Name: tipos_unidade tipos_unidade_empresa_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tipos_unidade
    ADD CONSTRAINT tipos_unidade_empresa_id_fkey FOREIGN KEY (empresa_id) REFERENCES public.empresas(id) ON DELETE CASCADE;


--
-- Name: unidades_empresa unidades_empresa_empresa_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unidades_empresa
    ADD CONSTRAINT unidades_empresa_empresa_id_fkey FOREIGN KEY (empresa_id) REFERENCES public.empresas(id) ON DELETE CASCADE;


--
-- Name: unidades_empresa unidades_empresa_tipo_unidade_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unidades_empresa
    ADD CONSTRAINT unidades_empresa_tipo_unidade_id_fkey FOREIGN KEY (tipo_unidade_id) REFERENCES public.tipos_unidade(id) ON DELETE RESTRICT;


--
-- Name: usuarios_areas usuarios_areas_area_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios_areas
    ADD CONSTRAINT usuarios_areas_area_id_fkey FOREIGN KEY (area_id) REFERENCES public.areas(id) ON DELETE CASCADE;


--
-- Name: usuarios_areas usuarios_areas_usuario_empresa_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios_areas
    ADD CONSTRAINT usuarios_areas_usuario_empresa_id_fkey FOREIGN KEY (usuario_empresa_id) REFERENCES public.usuarios_empresas(id) ON DELETE CASCADE;


--
-- Name: usuarios_empresas usuarios_empresas_empresa_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios_empresas
    ADD CONSTRAINT usuarios_empresas_empresa_id_fkey FOREIGN KEY (empresa_id) REFERENCES public.empresas(id) ON DELETE CASCADE;


--
-- Name: usuarios_empresas usuarios_empresas_perfil_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios_empresas
    ADD CONSTRAINT usuarios_empresas_perfil_id_fkey FOREIGN KEY (perfil_id) REFERENCES public.perfis(id);


--
-- Name: usuarios_empresas usuarios_empresas_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios_empresas
    ADD CONSTRAINT usuarios_empresas_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id) ON DELETE CASCADE;


--
-- Name: usuarios_tenants usuarios_tenants_perfil_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios_tenants
    ADD CONSTRAINT usuarios_tenants_perfil_id_fkey FOREIGN KEY (perfil_id) REFERENCES public.perfis(id);


--
-- Name: usuarios_tenants usuarios_tenants_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios_tenants
    ADD CONSTRAINT usuarios_tenants_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: usuarios_tenants usuarios_tenants_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios_tenants
    ADD CONSTRAINT usuarios_tenants_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id) ON DELETE CASCADE;


--
-- Name: usuarios_unidades usuarios_unidades_unidade_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios_unidades
    ADD CONSTRAINT usuarios_unidades_unidade_id_fkey FOREIGN KEY (unidade_id) REFERENCES public.unidades_empresa(id) ON DELETE CASCADE;


--
-- Name: usuarios_unidades usuarios_unidades_usuario_empresa_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios_unidades
    ADD CONSTRAINT usuarios_unidades_usuario_empresa_id_fkey FOREIGN KEY (usuario_empresa_id) REFERENCES public.usuarios_empresas(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict NIBIMLck5RIlimqrjEUrnqrsyJBo76ZoximTA6or2JeKtT1At3yKP1k4aZXn1Sh



