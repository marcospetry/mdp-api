# MDP Consultoria — Arquitetura Técnica

**Versão:** 0.1  
**Data:** 12/08/2026  
**Status:** Estado atual confirmado

## 1. Objetivo

Documentar a arquitetura técnica atual da plataforma MDP Consultoria, distinguindo o que está implementado, o que está planejado e o que ainda está pendente.

## 2. Estado atual

### IMPLEMENTADO

- VPS Ubuntu 24.04 na Hostinger.
- Dokploy como plataforma de deploy.
- Docker como runtime dos serviços.
- Traefik como reverse proxy.
- Domínio `api.mdpconsultoria.com.br`.
- HTTPS válido via Let's Encrypt.
- API em FastAPI/Uvicorn.
- PostgreSQL 17 exclusivo para a MDP API.
- Banco de dados `mdp`.
- Estrutura multiempresa.
- Estrutura de usuários, perfis e vínculo usuário/empresa.
- Estrutura de contatos.
- Estrutura do diagnóstico digital.
- Swagger disponível em `/docs`.
- Endpoint de health-check disponível em `/api/health`.

### PLANEJADO

- Endpoints CRUD da MDP API.
- API de contatos.
- API de empresas.
- API de usuários e autenticação.
- API de diagnóstico.
- Integração do formulário da landing page.
- Integração com serviços de e-mail.
- Integração com n8n.
- Integração futura com WhatsApp Business Cloud API.
- Integração futura com Chatwoot.
- Dashboards e métricas.
- Recursos de IA, RAG e agentes onde houver benefício real.

### PENDENTE

- Mapear as tabelas existentes em models SQLAlchemy.
- Criar schemas Pydantic.
- Criar routers FastAPI.
- Implementar autenticação/autorização.
- Definir políticas de acesso multiempresa.
- Definir versionamento/migrações de banco.
- Criar testes automatizados.
- Formalizar processo de deploy e rollback.
- Implementar observabilidade e logs de aplicação.

## 3. Infraestrutura

### VPS

- Provedor: Hostinger
- Sistema operacional: Ubuntu 24.04
- IPv4: `179.198.116.174`

### Containers identificados

| Componente | Container/Serviço | Tecnologia |
|---|---|---|
| MDP API | `mdpsite-mdpapi-*` | FastAPI/Uvicorn |
| Banco MDP | `mdpsite-mdppostgres-*` | PostgreSQL 17 |
| Proxy | `dokploy-traefik` | Traefik 3.6.7 |
| Dokploy | `dokploy.*` | Dokploy |
| Banco Dokploy | `dokploy-postgres.*` | PostgreSQL 16 |
| Kanban App | `kanban-kanban-lph8ja-app-1` | Aplicação Kanban |
| Kanban DB | `kanban-kanban-lph8ja-db-1` | PostgreSQL 16 Alpine |

## 4. Arquitetura lógica

```text
Internet
   |
   v
DNS
api.mdpconsultoria.com.br
   |
   v
VPS Hostinger
179.198.116.174
   |
   v
Traefik / HTTPS
   |
   v
MDP API
FastAPI + Uvicorn
porta interna 8000
   |
   v
SQLAlchemy
   |
   v
PostgreSQL 17
Banco: mdp
```

## 5. Aplicação FastAPI

Diretório local conhecido:

```text
D:\work\mdp-api
```

Estrutura atual:

```text
mdp-api/
├── .env
├── .gitignore
├── .venv/
├── app/
│   ├── config.py
│   ├── database.py
│   ├── main.py
│   ├── models/
│   │   └── __init__.py
│   ├── routers/
│   │   └── __init__.py
│   ├── schemas/
│   │   └── __init__.py
│   ├── services/
│   ├── __init__.py
│   └── __pycache__/
├── Dockerfile
└── requirements.txt
```

### `main.py`

Atualmente contém:

- título `MDP API`;
- versão `0.1.0`;
- endpoint `GET /api/health`.

### `database.py`

Atualmente utiliza:

- SQLAlchemy `create_engine`;
- `SessionLocal`;
- `Base = declarative_base()`;
- função `get_db()`.

### `config.py`

Atualmente utiliza `pydantic-settings` e lê configurações do `.env`.

Variáveis identificadas:

- `database_url`
- `secret_key`

Credenciais e senhas não devem ser documentadas em texto aberto.

## 6. Banco de dados

Banco confirmado:

```text
DATABASE=mdp
USER=mdp
PostgreSQL=17
```

Tabelas existentes:

1. `empresas`
2. `usuarios`
3. `perfis`
4. `usuarios_empresas`
5. `contatos`
6. `diagnosticos`
7. `categorias_diagnostico`
8. `perguntas_diagnostico`
9. `opcoes_pergunta_diagnostico`
10. `respostas_diagnostico`

## 7. Arquitetura funcional do banco

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

## 8. Multiempresa

A arquitetura já suporta multiempresa.

A tabela `empresas` é a entidade central. As principais tabelas de negócio utilizam `empresa_id` para separar dados por empresa.

O vínculo de usuários com empresas é feito por `usuarios_empresas`, que também define o perfil daquele usuário naquela empresa.

## 9. Diagnóstico digital

A estrutura existente permite:

- categorias de diagnóstico;
- perguntas;
- perguntas globais ou específicas por empresa;
- opções de resposta;
- peso por pergunta;
- nível;
- método de avaliação;
- pontuação;
- indicação se a pergunta gera achado;
- respostas por diagnóstico;
- pontuação total;
- classificação;
- controle de status e datas.

## 10. Arquitetura futura

```text
Landing Page
Site MDP
Diagnóstico Digital
WhatsApp / Chatbot
n8n / Automações
Aplicações de clientes
        |
        v
     MDP API
        |
        v
   PostgreSQL
```

Integrações futuras previstas:

- Chatwoot
- n8n
- WhatsApp Business Cloud API
- serviços de e-mail
- LLMs
- RAG
- agentes
- dashboards

## 11. Organização recomendada da API

```text
app/
├── models/      # mapeamento SQLAlchemy das tabelas
├── schemas/     # contratos Pydantic de entrada/saída
├── routers/     # endpoints HTTP
├── services/    # regras de negócio e integrações
├── database.py
├── config.py
└── main.py
```

## 12. Regras de evolução

Antes de qualquer alteração estrutural:

1. confirmar se o objeto já existe no banco;
2. documentar a alteração;
3. criar migration ou script versionado;
4. atualizar models/schemas/routers;
5. testar localmente;
6. publicar;
7. testar em produção;
8. atualizar esta documentação.

## 13. Documentos relacionados

- `ARQUITETURA.md`
- `BANCO_DE_DADOS.md`
- futuro `API.md`
- futuro `DEPLOY.md`


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
