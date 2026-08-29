# MDP — Estrutura Organizacional Multitenant v0.1

Data: 2026-08-28

## Objetivo

Introduzir a estrutura Empresa → Unidade opcional → Área opcional e o escopo organizacional de usuários, preservando autenticação, MFA, sessões e o CRUD existente.

## Banco

Migration: `database/004_estrutura_organizacional_multitenant.sql`

Cria:
- `tipos_unidade`: catálogo auxiliar global MDP + customizações por tenant.
- `unidades_empresa`: unidades opcionais da empresa.
- `areas`: áreas diretas da empresa (`unidade_id=NULL`) ou de uma unidade.
- `usuarios_unidades`: vínculos explícitos de acesso.
- `usuarios_areas`: vínculos explícitos de acesso.

Altera `usuarios_empresas`:
- `acesso_todas_unidades BOOLEAN NOT NULL DEFAULT FALSE`
- `acesso_todas_areas BOOLEAN NOT NULL DEFAULT FALSE`

Tipos globais iniciais: MATRIZ, FILIAL, ESCRITORIO, LOJA, QUIOSQUE, FABRICA, DISTRIBUIDORA, CENTRO_DISTRIBUICAO, DEPOSITO, POSTO_ATENDIMENTO, HOME_OFFICE e OUTRO.

## Regras

- Empresa pode ter zero, uma ou várias unidades.
- Área pode pertencer diretamente à empresa ou a uma unidade.
- CNPJ de unidade é opcional e, quando preenchido, é único de forma normalizada.
- Tipos padrão MDP são protegidos; tenants podem criar seus próprios tipos.
- Não há DELETE físico para cadastros organizacionais via API; usa-se status `ativo`.
- Vínculos `usuarios_unidades` e `usuarios_areas` podem ser removidos fisicamente por serem autorizações, não histórico de negócio.
- Perfil define **o que** o usuário pode fazer; Empresa/Unidade/Área definem **onde**.
- `acesso_todas_unidades` e `acesso_todas_areas` são independentes.
- API valida que tipos, unidades, áreas e vínculos pertencem ao tenant correto.

## APIs adicionadas

- `GET /api/admin/empresas/{empresa_id}/tipos-unidade`
- `POST /api/admin/empresas/{empresa_id}/tipos-unidade`
- `PUT /api/admin/tipos-unidade/{tipo_id}`
- `PATCH /api/admin/tipos-unidade/{tipo_id}/status`
- `GET /api/admin/empresas/{empresa_id}/unidades`
- `POST /api/admin/empresas/{empresa_id}/unidades`
- `GET /api/admin/unidades/{unidade_id}`
- `PUT /api/admin/unidades/{unidade_id}`
- `PATCH /api/admin/unidades/{unidade_id}/status`
- `GET /api/admin/empresas/{empresa_id}/areas`
- `POST /api/admin/empresas/{empresa_id}/areas`
- `GET /api/admin/areas/{area_id}`
- `PUT /api/admin/areas/{area_id}`
- `PATCH /api/admin/areas/{area_id}/status`
- `PATCH /api/admin/usuarios-empresas/{vinculo_id}/escopo`
- `POST/DELETE /api/admin/usuarios-empresas/{vinculo_id}/unidades[...]`
- `POST/DELETE /api/admin/usuarios-empresas/{vinculo_id}/areas[...]`

## Isolamento multiempresa

O CRUD existente de Empresas/Contatos foi reforçado:
- superadmin continua com visão global;
- usuário comum fica limitado à empresa ativa do token;
- UUID de outra empresa não concede acesso;
- criação de novos tenants e promoção de contato para nova empresa ficam reservadas ao superadmin MDP.

## Formulários e diagnósticos

Nenhuma tabela de formulário/diagnóstico foi alterada nesta versão. A decisão arquitetural é manter o formulário reutilizável e, em etapa posterior, aplicar Empresa/Unidade/Área no contexto da execução. Isso permitirá diagnóstico MDP, pesquisa interna, auditoria, checklist e outras aplicações sem acoplar o formulário à estrutura organizacional.

## Validação antes de produção

1. Backup do banco.
2. Aplicar a migration primeiro em ambiente de teste/local conectado ao banco de teste.
3. Conferir 12 tipos globais.
4. Validar criação de unidade e área direta/local.
5. Validar vínculo e revogação de escopo de usuário.
6. Testar tentativa de acesso cruzado entre dois tenants.
7. Reexecutar smoke tests existentes de autenticação, Empresas/Contatos e Form Builder.
8. Somente após aprovação publicar em produção.

## Observação de empacotamento

O ZIP de entrega não inclui `.env`, `.venv` nem `__pycache__`. Preserve o `.env` local/produção já existente; não substitua credenciais por arquivos de pacote.
