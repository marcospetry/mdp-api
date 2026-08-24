-- MDP Diagnóstico - Migration 003
-- Adequação estrutural para o modelo de diagnóstico por estados
-- Data: 2026-08-24

BEGIN;

-- 1. perguntas_diagnostico
ALTER TABLE perguntas_diagnostico
    ADD COLUMN IF NOT EXISTS natureza VARCHAR(20),
    ADD COLUMN IF NOT EXISTS ideal TEXT,
    ADD COLUMN IF NOT EXISTS sugestao TEXT;

UPDATE perguntas_diagnostico
SET natureza = 'CONTEXTO'
WHERE natureza IS NULL;

ALTER TABLE perguntas_diagnostico
    ALTER COLUMN natureza SET DEFAULT 'CONTEXTO',
    ALTER COLUMN natureza SET NOT NULL;

ALTER TABLE perguntas_diagnostico
    DROP CONSTRAINT IF EXISTS ck_perguntas_diagnostico_natureza;

ALTER TABLE perguntas_diagnostico
    ADD CONSTRAINT ck_perguntas_diagnostico_natureza
    CHECK (natureza IN ('AVALIATIVA', 'CONTEXTO'));

ALTER TABLE perguntas_diagnostico
    DROP CONSTRAINT IF EXISTS ck_perguntas_diagnostico_tipo_resposta;

ALTER TABLE perguntas_diagnostico
    ADD CONSTRAINT ck_perguntas_diagnostico_tipo_resposta
    CHECK (
        tipo_resposta IN (
            'ESCOLHA_UNICA',
            'MULTIPLA_ESCOLHA',
            'NUMERO',
            'TEXTO_CURTO'
        )
    );

ALTER TABLE perguntas_diagnostico
    DROP CONSTRAINT IF EXISTS ck_perguntas_diagnostico_tipo_natureza;

ALTER TABLE perguntas_diagnostico
    ADD CONSTRAINT ck_perguntas_diagnostico_tipo_natureza
    CHECK (
        NOT (
            tipo_resposta IN ('MULTIPLA_ESCOLHA', 'TEXTO_CURTO')
            AND natureza <> 'CONTEXTO'
        )
    );

-- 2. opcoes_pergunta_diagnostico
ALTER TABLE opcoes_pergunta_diagnostico
    ADD COLUMN IF NOT EXISTS estado_interno VARCHAR(20);

ALTER TABLE opcoes_pergunta_diagnostico
    DROP CONSTRAINT IF EXISTS ck_opcoes_pergunta_estado_interno;

ALTER TABLE opcoes_pergunta_diagnostico
    ADD CONSTRAINT ck_opcoes_pergunta_estado_interno
    CHECK (
        estado_interno IS NULL
        OR estado_interno IN ('ALTO', 'MEDIO', 'BAIXO', 'NA', 'NAO_SEI')
    );

CREATE UNIQUE INDEX IF NOT EXISTS uq_opcoes_pergunta_estado_interno
ON opcoes_pergunta_diagnostico (pergunta_id, estado_interno)
WHERE estado_interno IS NOT NULL;

-- 3. respostas_diagnostico
ALTER TABLE respostas_diagnostico
    ADD COLUMN IF NOT EXISTS opcao_id UUID,
    ADD COLUMN IF NOT EXISTS estado_interno VARCHAR(20);

ALTER TABLE respostas_diagnostico
    DROP CONSTRAINT IF EXISTS fk_respostas_diagnostico_opcao;

ALTER TABLE respostas_diagnostico
    ADD CONSTRAINT fk_respostas_diagnostico_opcao
    FOREIGN KEY (opcao_id)
    REFERENCES opcoes_pergunta_diagnostico(id);

ALTER TABLE respostas_diagnostico
    DROP CONSTRAINT IF EXISTS ck_respostas_diagnostico_estado_interno;

ALTER TABLE respostas_diagnostico
    ADD CONSTRAINT ck_respostas_diagnostico_estado_interno
    CHECK (
        estado_interno IS NULL
        OR estado_interno IN ('ALTO', 'MEDIO', 'BAIXO', 'NA', 'NAO_SEI')
    );

CREATE INDEX IF NOT EXISTS ix_respostas_diagnostico_opcao_id
ON respostas_diagnostico(opcao_id);

CREATE INDEX IF NOT EXISTS ix_respostas_diagnostico_estado_interno
ON respostas_diagnostico(estado_interno);

-- 4. faixas_avaliacao_numero
CREATE TABLE IF NOT EXISTS faixas_avaliacao_numero (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pergunta_id UUID NOT NULL,
    valor_min NUMERIC(15,4),
    valor_max NUMERIC(15,4),
    estado_interno VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT fk_faixas_avaliacao_numero_pergunta
        FOREIGN KEY (pergunta_id)
        REFERENCES perguntas_diagnostico(id)
        ON DELETE CASCADE,

    CONSTRAINT ck_faixas_avaliacao_numero_estado
        CHECK (estado_interno IN ('ALTO', 'MEDIO', 'BAIXO', 'NA', 'NAO_SEI')),

    CONSTRAINT ck_faixas_avaliacao_numero_limites
        CHECK (
            valor_min IS NULL
            OR valor_max IS NULL
            OR valor_min <= valor_max
        )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_faixas_avaliacao_numero_pergunta_estado
ON faixas_avaliacao_numero (pergunta_id, estado_interno);

CREATE INDEX IF NOT EXISTS ix_faixas_avaliacao_numero_pergunta
ON faixas_avaliacao_numero(pergunta_id);

-- 5. regras_exibicao_perguntas
CREATE TABLE IF NOT EXISTS regras_exibicao_perguntas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    formulario_id UUID NOT NULL,
    pergunta_origem_id UUID NOT NULL,
    opcao_origem_id UUID NOT NULL,
    pergunta_destino_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT fk_regras_exibicao_formulario
        FOREIGN KEY (formulario_id)
        REFERENCES formularios_diagnostico(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_regras_exibicao_pergunta_origem
        FOREIGN KEY (pergunta_origem_id)
        REFERENCES perguntas_diagnostico(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_regras_exibicao_opcao_origem
        FOREIGN KEY (opcao_origem_id)
        REFERENCES opcoes_pergunta_diagnostico(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_regras_exibicao_pergunta_destino
        FOREIGN KEY (pergunta_destino_id)
        REFERENCES perguntas_diagnostico(id)
        ON DELETE CASCADE,

    CONSTRAINT ck_regras_exibicao_perguntas_distintas
        CHECK (pergunta_origem_id <> pergunta_destino_id),

    CONSTRAINT uq_regras_exibicao_perguntas
        UNIQUE (
            formulario_id,
            pergunta_origem_id,
            opcao_origem_id,
            pergunta_destino_id
        )
);

CREATE INDEX IF NOT EXISTS ix_regras_exibicao_formulario
ON regras_exibicao_perguntas(formulario_id);

CREATE INDEX IF NOT EXISTS ix_regras_exibicao_origem
ON regras_exibicao_perguntas(pergunta_origem_id, opcao_origem_id);

CREATE INDEX IF NOT EXISTS ix_regras_exibicao_destino
ON regras_exibicao_perguntas(pergunta_destino_id);

-- 6. respostas_diagnostico_opcoes
CREATE TABLE IF NOT EXISTS respostas_diagnostico_opcoes (
    resposta_id UUID NOT NULL,
    opcao_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT pk_respostas_diagnostico_opcoes
        PRIMARY KEY (resposta_id, opcao_id),

    CONSTRAINT fk_respostas_diagnostico_opcoes_resposta
        FOREIGN KEY (resposta_id)
        REFERENCES respostas_diagnostico(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_respostas_diagnostico_opcoes_opcao
        FOREIGN KEY (opcao_id)
        REFERENCES opcoes_pergunta_diagnostico(id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_respostas_diagnostico_opcoes_opcao
ON respostas_diagnostico_opcoes(opcao_id);

-- 7. validação opção x pergunta
CREATE OR REPLACE FUNCTION fn_validar_opcao_pergunta_diagnostico()
RETURNS TRIGGER
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
        RAISE EXCEPTION 'Pergunta % não encontrada', NEW.pergunta_id;
    END IF;

    IF v_natureza = 'CONTEXTO' AND NEW.estado_interno IS NOT NULL THEN
        RAISE EXCEPTION 'Pergunta CONTEXTO não aceita estado_interno';
    END IF;

    IF v_tipo_resposta IN ('NUMERO', 'TEXTO_CURTO') THEN
        RAISE EXCEPTION
            'Pergunta do tipo % não utiliza opcoes_pergunta_diagnostico',
            v_tipo_resposta;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_validar_opcao_pergunta_diagnostico
ON opcoes_pergunta_diagnostico;

CREATE TRIGGER trg_validar_opcao_pergunta_diagnostico
BEFORE INSERT OR UPDATE
ON opcoes_pergunta_diagnostico
FOR EACH ROW
EXECUTE FUNCTION fn_validar_opcao_pergunta_diagnostico();

-- 8. validação faixas numéricas
CREATE OR REPLACE FUNCTION fn_validar_faixa_avaliacao_numero()
RETURNS TRIGGER
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
        RAISE EXCEPTION 'Pergunta % não encontrada', NEW.pergunta_id;
    END IF;

    IF v_tipo_resposta <> 'NUMERO' THEN
        RAISE EXCEPTION
            'Faixa de avaliação só pode ser cadastrada para pergunta NUMERO';
    END IF;

    IF v_natureza <> 'AVALIATIVA' THEN
        RAISE EXCEPTION
            'Faixa de avaliação só pode ser cadastrada para pergunta NUMERO AVALIATIVA';
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
            'Faixa numérica sobrepõe outra faixa existente para esta pergunta';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_validar_faixa_avaliacao_numero
ON faixas_avaliacao_numero;

CREATE TRIGGER trg_validar_faixa_avaliacao_numero
BEFORE INSERT OR UPDATE
ON faixas_avaliacao_numero
FOR EACH ROW
EXECUTE FUNCTION fn_validar_faixa_avaliacao_numero();

-- 9. validação regra de exibição
CREATE OR REPLACE FUNCTION fn_validar_regra_exibicao_pergunta()
RETURNS TRIGGER
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
            'opcao_origem_id não pertence à pergunta_origem_id informada';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM formularios_perguntas fp
        WHERE fp.formulario_id = NEW.formulario_id
          AND fp.pergunta_id = NEW.pergunta_origem_id
          AND fp.ativo = true
    ) THEN
        RAISE EXCEPTION
            'Pergunta de origem não está ativa no formulário informado';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM formularios_perguntas fp
        WHERE fp.formulario_id = NEW.formulario_id
          AND fp.pergunta_id = NEW.pergunta_destino_id
          AND fp.ativo = true
    ) THEN
        RAISE EXCEPTION
            'Pergunta de destino não está ativa no formulário informado';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_validar_regra_exibicao_pergunta
ON regras_exibicao_perguntas;

CREATE TRIGGER trg_validar_regra_exibicao_pergunta
BEFORE INSERT OR UPDATE
ON regras_exibicao_perguntas
FOR EACH ROW
EXECUTE FUNCTION fn_validar_regra_exibicao_pergunta();

COMMIT;

-- Validação pós-migration

SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND (
       (table_name = 'perguntas_diagnostico'
        AND column_name IN ('natureza','ideal','sugestao'))
    OR (table_name = 'opcoes_pergunta_diagnostico'
        AND column_name = 'estado_interno')
    OR (table_name = 'respostas_diagnostico'
        AND column_name IN ('opcao_id','estado_interno'))
  )
ORDER BY table_name, ordinal_position;

SELECT
    to_regclass('public.faixas_avaliacao_numero')      AS faixas_avaliacao_numero,
    to_regclass('public.regras_exibicao_perguntas')    AS regras_exibicao_perguntas,
    to_regclass('public.respostas_diagnostico_opcoes') AS respostas_diagnostico_opcoes;
