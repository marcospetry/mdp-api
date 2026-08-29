# MDP — Manutenção: Origens de Contato e Tipos de Interação v0.1

Implementação DEV local. Não aplicar na VPS antes da validação/aprovação.

## Incluído
- migration `database/005_origens_tipos_interacao.sql`;
- tabelas `origens_contato` e `tipos_interacao`;
- FK `contatos.origem_contato_id`;
- FK `interacoes.tipo_interacao_id`;
- APIs administrativas de listar/criar/editar/ativar-inativar;
- menu **Manutenção** com os dois CRUDs;
- campo **Origem do contato** no CRUD de Contatos como select;
- formulário público passa a resolver a origem global `SITE` e o tipo `FORMULARIO_SITE`;
- campos textuais legados permanecem por compatibilidade;
- DEV_AUTH abre o Admin local sem login/MFA; produção continua com autenticação normal.

## Ordem de validação
1. aplicar migration 005 somente no PostgreSQL DEV local;
2. reiniciar Uvicorn;
3. executar `python scripts\\smoke_test_manutencao_local.py`;
4. abrir `/admin` e validar Manutenção + Contatos;
5. somente após aprovação preparar produção.
