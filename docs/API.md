# MDP Consultoria — API

**Versão do documento:** 0.1  
**Data:** 12/08/2026  
**Status:** Estado atual confirmado + próximos endpoints planejados

## 1. Visão geral

A MDP API é a camada de serviços da plataforma MDP Consultoria.

Tecnologias confirmadas:

- Python
- FastAPI
- Uvicorn
- SQLAlchemy
- Pydantic Settings
- PostgreSQL 17

URL pública:

`https://api.mdpconsultoria.com.br`

Swagger:

`https://api.mdpconsultoria.com.br/docs`

## 2. Endpoint atualmente implementado

### GET `/api/health`

Objetivo: validar disponibilidade básica da API.

Resposta atual:

```json
{
  "status": "ok",
  "service": "mdp-api",
  "version": "0.1.0"
}
```

## 3. Estrutura atual da aplicação

```text
app/
├── config.py
├── database.py
├── main.py
├── models/
├── routers/
├── schemas/
└── services/
```

No estado atual confirmado:

- `models` ainda não possui models de negócio implementados;
- `routers` ainda não possui routers de negócio implementados;
- `schemas` ainda não possui schemas de negócio implementados;
- `main.py` contém apenas a configuração básica da aplicação e o health-check.

## 4. Banco disponível para a API

Banco: `mdp`

Tabelas existentes:

- empresas
- usuarios
- perfis
- usuarios_empresas
- contatos
- diagnosticos
- categorias_diagnostico
- perguntas_diagnostico
- opcoes_pergunta_diagnostico
- respostas_diagnostico

## 5. Endpoints planejados

### Contatos

Planejado inicialmente:

- `POST /api/contatos`
- `GET /api/contatos`
- `GET /api/contatos/{id}`
- `PATCH /api/contatos/{id}`

Objetivo:

- receber contatos da landing page/site;
- armazenar lead;
- identificar empresa;
- controlar origem e status;
- permitir evolução posterior para notificações e funil comercial.

### Empresas

Planejado:

- consulta;
- cadastro;
- atualização;
- ativação/inativação.

### Usuários

Planejado:

- autenticação;
- consulta;
- associação com empresas;
- perfis e permissões.

### Diagnóstico

Planejado:

- iniciar diagnóstico;
- listar categorias;
- listar perguntas;
- registrar respostas;
- calcular pontuação;
- concluir diagnóstico;
- classificar resultado.

## 6. Convenções recomendadas

Prefixo padrão:

`/api`

Formato:

`application/json`

IDs:

UUID

Datas:

ISO 8601

Erros:

respostas HTTP padronizadas com mensagem clara.

## 7. Segurança prevista

Ainda pendente de implementação:

- autenticação;
- autorização;
- segregação por empresa;
- proteção de endpoints administrativos;
- rate limit para endpoints públicos;
- CORS controlado;
- logs sem exposição de credenciais.

## 8. Regra de evolução

Antes de adicionar um endpoint:

1. confirmar a tabela existente;
2. definir contrato de entrada e saída;
3. criar model SQLAlchemy;
4. criar schema Pydantic;
5. criar router;
6. separar regra de negócio em service quando necessário;
7. testar localmente;
8. publicar;
9. testar produção;
10. atualizar este documento.

## 9. Próxima implementação

Prioridade imediata:

`POST /api/contatos`

A implementação deverá utilizar a tabela `contatos` já existente, sem recriar sua estrutura.
