# MDP Consultoria — Banco de Dados

**Banco:** `mdp`  
**PostgreSQL:** 17  
**Usuário do banco:** `mdp`  
**Data do inventário:** 12/08/2026  
**Total de tabelas:** 10

## 1. Visão geral

O banco foi estruturado para suportar:

- multiempresa;
- usuários e perfis;
- contatos/leads;
- diagnóstico digital;
- categorias e perguntas;
- opções de resposta;
- respostas e pontuação.

## 2. Diagrama lógico simplificado

```text
empresas
 ├── usuarios_empresas ── usuarios
 │                     └─ perfis
 ├── contatos
 ├── diagnosticos
 │    └── respostas_diagnostico
 ├── categorias_diagnostico
 │    └── perguntas_diagnostico
 │         ├── opcoes_pergunta_diagnostico
 │         └── respostas_diagnostico
 └── perguntas_diagnostico
```

---

## 3. Tabela `empresas`

Representa cada empresa/tenant da plataforma.

| Campo | Tipo | Nulo | Default |
|---|---|---:|---|
| id | uuid | não | `gen_random_uuid()` |
| nome | varchar(150) | não | |
| slug | varchar(80) | não | |
| cnpj | varchar(20) | sim | |
| email | varchar(150) | sim | |
| telefone | varchar(30) | sim | |
| dominio | varchar(255) | sim | |
| ativo | boolean | não | true |
| created_at | timestamptz | não | now() |
| updated_at | timestamptz | não | now() |

### Chaves e índices

- PK: `empresas_pkey (id)`
- UNIQUE: `empresas_slug_key (slug)`

### Referenciada por

- `categorias_diagnostico.empresa_id`
- `contatos.empresa_id`
- `diagnosticos.empresa_id`
- `perguntas_diagnostico.empresa_id`
- `usuarios_empresas.empresa_id`

---

## 4. Tabela `usuarios`

Cadastro de usuários da plataforma.

| Campo | Tipo | Nulo | Default |
|---|---|---:|---|
| id | uuid | não | `gen_random_uuid()` |
| nome | varchar(150) | não | |
| email | varchar(150) | não | |
| password_hash | text | não | |
| is_superadmin | boolean | não | false |
| ativo | boolean | não | true |
| ultimo_login_em | timestamptz | sim | |
| created_at | timestamptz | não | now() |
| updated_at | timestamptz | não | now() |

### Chaves e índices

- PK: `usuarios_pkey (id)`
- UNIQUE: `usuarios_email_key (email)`

### Referenciada por

- `usuarios_empresas.usuario_id`

---

## 5. Tabela `perfis`

Perfis de acesso.

| Campo | Tipo | Nulo | Default |
|---|---|---:|---|
| id | uuid | não | `gen_random_uuid()` |
| codigo | varchar(40) | não | |
| nome | varchar(80) | não | |
| descricao | text | sim | |
| ativo | boolean | não | true |
| created_at | timestamptz | não | now() |
| updated_at | timestamptz | não | now() |

### Chaves e índices

- PK: `perfis_pkey (id)`
- UNIQUE: `perfis_codigo_key (codigo)`

### Referenciada por

- `usuarios_empresas.perfil_id`

---

## 6. Tabela `usuarios_empresas`

Tabela associativa entre usuários e empresas, incluindo o perfil do usuário dentro de cada empresa.

| Campo | Tipo | Nulo | Default |
|---|---|---:|---|
| id | uuid | não | `gen_random_uuid()` |
| usuario_id | uuid | não | |
| empresa_id | uuid | não | |
| perfil_id | uuid | não | |
| ativo | boolean | não | true |
| created_at | timestamptz | não | now() |

### Chaves

- PK: `usuarios_empresas_pkey (id)`
- UNIQUE: `(usuario_id, empresa_id)`

### FKs

- `usuario_id -> usuarios(id)` ON DELETE CASCADE
- `empresa_id -> empresas(id)` ON DELETE CASCADE
- `perfil_id -> perfis(id)`

### Índices

- `idx_usuarios_empresas_empresa (empresa_id)`
- `idx_usuarios_empresas_usuario (usuario_id)`

---

## 7. Tabela `contatos`

Armazena contatos/leads recebidos pela MDP ou por empresas clientes.

| Campo | Tipo | Nulo | Default |
|---|---|---:|---|
| id | uuid | não | `gen_random_uuid()` |
| empresa_id | uuid | não | |
| nome | varchar(150) | não | |
| email | varchar(150) | não | |
| telefone | varchar(30) | sim | |
| empresa_contato | varchar(150) | sim | |
| mensagem | text | não | |
| origem | varchar(50) | não | `'site'` |
| status | varchar(30) | não | `'novo'` |
| created_at | timestamptz | não | now() |
| updated_at | timestamptz | não | now() |

### PK

- `contatos_pkey (id)`

### FK

- `empresa_id -> empresas(id)`

### Índices

- `idx_contatos_empresa_id (empresa_id)`
- `idx_contatos_empresa_status (empresa_id, status)`

---

## 8. Tabela `diagnosticos`

Cabeçalho de cada diagnóstico realizado.

| Campo | Tipo | Nulo | Default |
|---|---|---:|---|
| id | uuid | não | `gen_random_uuid()` |
| empresa_id | uuid | não | |
| nome_contato | varchar(150) | sim | |
| email_contato | varchar(150) | sim | |
| telefone_contato | varchar(30) | sim | |
| empresa_avaliada | varchar(150) | sim | |
| status | varchar(30) | não | `'em_andamento'` |
| pontuacao_total | numeric(10,2) | sim | |
| classificacao | varchar(50) | sim | |
| iniciado_em | timestamptz | não | now() |
| concluido_em | timestamptz | sim | |
| created_at | timestamptz | não | now() |
| updated_at | timestamptz | não | now() |

### PK

- `diagnosticos_pkey (id)`

### FK

- `empresa_id -> empresas(id)`

### Índice

- `idx_diagnosticos_empresa (empresa_id)`

### Referenciada por

- `respostas_diagnostico.diagnostico_id`

---

## 9. Tabela `categorias_diagnostico`

Categorias usadas para agrupar perguntas do diagnóstico.

| Campo | Tipo | Nulo | Default |
|---|---|---:|---|
| id | uuid | não | `gen_random_uuid()` |
| empresa_id | uuid | sim | |
| nome | varchar(120) | não | |
| descricao | text | sim | |
| ordem | integer | não | 0 |
| ativo | boolean | não | true |
| created_at | timestamptz | não | now() |
| updated_at | timestamptz | não | now() |

### PK

- `categorias_diagnostico_pkey (id)`

### FK

- `empresa_id -> empresas(id)`

### Índice

- `idx_categorias_empresa (empresa_id)`

### Referenciada por

- `perguntas_diagnostico.categoria_id`

### Observação

Como `empresa_id` aceita `NULL`, a estrutura permite categorias globais e categorias específicas por empresa.

---

## 10. Tabela `perguntas_diagnostico`

Perguntas utilizadas no diagnóstico.

| Campo | Tipo | Nulo | Default |
|---|---|---:|---|
| id | uuid | não | `gen_random_uuid()` |
| empresa_id | uuid | sim | |
| categoria_id | uuid | não | |
| pergunta | text | não | |
| tipo_resposta | varchar(30) | não | |
| nivel | varchar(20) | não | `'basico'` |
| peso | numeric(10,2) | não | 1 |
| ordem | integer | não | 0 |
| obrigatoria | boolean | não | false |
| ativo | boolean | não | true |
| created_at | timestamptz | não | now() |
| updated_at | timestamptz | não | now() |
| codigo | varchar(30) | sim | |
| metodo_avaliacao | varchar(20) | não | `'cliente'` |
| ajuda | text | sim | |
| gera_achado | boolean | não | true |

### PK

- `perguntas_diagnostico_pkey (id)`

### FKs

- `categoria_id -> categorias_diagnostico(id)`
- `empresa_id -> empresas(id)`

### Índices

- `idx_perguntas_categoria (categoria_id)`
- `idx_perguntas_empresa (empresa_id)`

### Restrição única

- `uq_perguntas_codigo_global`
- UNIQUE em `codigo` quando `codigo IS NOT NULL AND empresa_id IS NULL`

### Referenciada por

- `opcoes_pergunta_diagnostico.pergunta_id`
- `respostas_diagnostico.pergunta_id`

### Observação

A tabela já suporta conceitos importantes para a metodologia:

- nível;
- peso;
- obrigatoriedade;
- método de avaliação;
- ajuda;
- geração de achado;
- perguntas globais ou específicas por empresa.

---

## 11. Tabela `opcoes_pergunta_diagnostico`

Opções possíveis para perguntas de escolha.

| Campo | Tipo | Nulo | Default |
|---|---|---:|---|
| id | uuid | não | `gen_random_uuid()` |
| pergunta_id | uuid | não | |
| valor | varchar(80) | não | |
| rotulo | varchar(150) | não | |
| pontuacao | numeric(10,2) | não | 0 |
| ordem | integer | não | 0 |
| ativo | boolean | não | true |
| created_at | timestamptz | não | now() |
| updated_at | timestamptz | não | now() |

### PK

- `opcoes_pergunta_diagnostico_pkey (id)`

### FK

- `pergunta_id -> perguntas_diagnostico(id)` ON DELETE CASCADE

### Índice

- `idx_opcoes_pergunta (pergunta_id)`

### UNIQUE

- `(pergunta_id, valor)`

---

## 12. Tabela `respostas_diagnostico`

Armazena as respostas associadas a um diagnóstico.

| Campo | Tipo | Nulo | Default |
|---|---|---:|---|
| id | uuid | não | `gen_random_uuid()` |
| diagnostico_id | uuid | não | |
| pergunta_id | uuid | não | |
| resposta_texto | text | sim | |
| resposta_numero | numeric(15,4) | sim | |
| resposta_boolean | boolean | sim | |
| pontuacao | numeric(10,2) | sim | |
| observacao | text | sim | |
| created_at | timestamptz | não | now() |
| updated_at | timestamptz | não | now() |

### PK

- `respostas_diagnostico_pkey (id)`

### FKs

- `diagnostico_id -> diagnosticos(id)` ON DELETE CASCADE
- `pergunta_id -> perguntas_diagnostico(id)`

### Índice

- `idx_respostas_diagnostico (diagnostico_id)`

### UNIQUE

- `(diagnostico_id, pergunta_id)`

Isso impede mais de uma resposta para a mesma pergunta dentro do mesmo diagnóstico.

---

## 13. Relacionamentos principais

### Empresas e usuários

```text
usuarios
   |
   v
usuarios_empresas
   |
   +----> empresas
   |
   +----> perfis
```

O mesmo usuário pode pertencer a diferentes empresas, com um perfil associado a cada vínculo.

### Diagnóstico

```text
categorias_diagnostico
        |
        v
perguntas_diagnostico
        |
        +----> opcoes_pergunta_diagnostico
        |
        +----> respostas_diagnostico
                       ^
                       |
                 diagnosticos
```

## 14. Pontos já suportados pela modelagem

- multiempresa;
- usuário em múltiplas empresas;
- perfil por empresa;
- contatos por empresa;
- perguntas globais;
- perguntas customizadas por empresa;
- categorias customizadas;
- pesos;
- pontuação;
- diferentes tipos de resposta;
- perguntas obrigatórias;
- perguntas que geram achados;
- classificação final;
- diagnóstico em andamento/concluído.

## 15. Pontos a definir

Ainda devem ser formalizadas as regras para:

- valores aceitos em `tipo_resposta`;
- valores aceitos em `nivel`;
- valores aceitos em `metodo_avaliacao`;
- valores aceitos em `status` de contatos;
- valores aceitos em `status` de diagnósticos;
- fórmula de cálculo da pontuação total;
- regras de classificação;
- tratamento de achados;
- ligação futura com FTDs;
- auditoria de alterações;
- histórico de status;
- versionamento das perguntas do diagnóstico.

## 16. Regra para alterações futuras

Nenhuma alteração estrutural deve ser feita diretamente em produção sem:

1. documentação;
2. script/migration versionado;
3. teste;
4. backup;
5. aplicação controlada;
6. validação pós-deploy.


---

## Evolução 17/08/2026 — contatos e interações

### Decisão

A base MDP não será uma cópia integral do Chatwoot. O Chatwoot continua sendo a caixa operacional e pode receber mensagens sem valor cadastral, como testes, spam, trotes ou um simples “oi” ainda não qualificado.

O formulário do site é diferente: seu envio é uma manifestação explícita de interesse. Por isso, `POST /api/contatos` continua criando o contato diretamente na base MDP e passa a criar, na mesma transação, uma linha em `interacoes`.

### Regras implementadas

- `contatos` representa a pessoa/contato conhecido pela MDP;
- `interacoes` representa ocorrências relevantes associadas ao contato;
- formulário do site cria `contato + interação` atomicamente;
- WhatsApp/e-mail/Instagram via Chatwoot somente deverão entrar na base MDP após qualificação;
- `chatwoot_contact_id` permite vinculação futura sem obrigar todos os contatos a nascerem no Chatwoot;
- `origem_primeiro_contato` preserva aquisição e `origem_ultimo_contato` permite acompanhar o canal mais recente;
- `diagnosticos.contato_id`, criado pela Migration 001, passa a permitir o vínculo entre diagnóstico e contato oficial.

### Compatibilidade

Os campos legados do formulário em `contatos` não foram removidos nesta fase. Isso evita quebrar o site e a API existentes. A separação definitiva desses dados poderá ocorrer em migration futura, depois que o novo fluxo estiver estabilizado.

### Transação do formulário

Fluxo atual:

```text
POST /api/contatos
  -> INSERT contatos
  -> flush (obtém contato.id sem commit)
  -> INSERT interacoes
  -> commit único
  -> envio de e-mails em background
```

Assim, se a criação da interação falhar, o contato também não é confirmado parcialmente.
