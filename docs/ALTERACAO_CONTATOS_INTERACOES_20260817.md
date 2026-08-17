# MDP API — Alteração Contatos + Interações — 17/08/2026

## Motivo

O cadastro `contatos` nasceu para o formulário do site. Com a adoção do Chatwoot, nem toda mensagem recebida deve virar contato oficial da MDP. O Chatwoot recebe tudo; a base MDP guarda contatos relevantes/qualificados.

## Decisão funcional

- Formulário do site: cria contato diretamente, pois o preenchimento demonstra interesse.
- WhatsApp, e-mail e Instagram via Chatwoot: não criam contato automaticamente nesta fase; haverá qualificação antes da gravação.
- Spam, testes, trotes e mensagens sem contexto podem permanecer apenas no Chatwoot.
- Uma mesma pessoa não deve ser duplicada por possuir várias interações.

## Alterações no código

1. Novo model `app/models/interacao.py`, refletindo a tabela `interacoes` criada pela Migration 001.
2. `Contato.email` e `Contato.mensagem` passam a refletir a nulabilidade atual do banco.
3. `Contato` passa a mapear `chatwoot_contact_id`, `origem_primeiro_contato` e `origem_ultimo_contato`.
4. `POST /api/contatos` passa a criar contato e interação `FORMULARIO_SITE` em um único commit.
5. E-mails continuam sendo enfileirados somente depois do commit bem-sucedido.

## Banco necessário

Esta versão pressupõe que `MDP_Migration_001.sql` já foi aplicada. Em 17/08/2026 ela foi validada em produção com:

- tabela `interacoes` criada;
- 11 interações históricas migradas;
- `diagnosticos.contato_id` criado;
- índices de Chatwoot/deduplicação criados.

## Teste de aceite

Antes do deploy foi observado:

```text
contatos = 12
interacoes = 11
```

Após o deploy, enviar um novo formulário. Esperado:

```text
contatos = 13
interacoes = 12
```

Além disso, o contato novo deve possuir uma interação com:

```text
canal = SITE
origem = formulario_site
tipo_interacao = FORMULARIO_SITE
direcao = ENTRADA
classificacao = CONTATO ou DIAGNOSTICO
```

## Fora do escopo desta alteração

- ingestão automática de eventos do Chatwoot;
- n8n;
- classificação automática por IA;
- CRM/oportunidades/propostas/contratos;
- remoção dos campos legados do formulário em `contatos`.
