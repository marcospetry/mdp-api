# HOTFIX — Proteção dos CRUDs do Diagnóstico

Arquivos alterados:

- `app/routers/diagnostico_catalogo.py`
- `app/routers/diagnostico_formularios.py`

Arquivo de teste:

- `scripts/test_protecao_diagnostico.py`

## Regra aplicada

Foi adicionada dependência de autenticação no nível do `APIRouter`:

```python
dependencies=[Depends(get_current_context)]
```

Isso protege todos os endpoints registrados nesses dois routers.

Sem Bearer token válido, a API deve responder `401 Unauthorized`.

## Não alterado

- `/api/health`
- `/api/contatos`
- `/api/auth/login`
- MFA
- refresh
- banco
- migrations
- `.env`
- `.git`
- `.venv`

## Observação

Este hotfix fecha a porta dos CRUDs administrativos do Diagnóstico.
A granularidade por permissão (`diagnosticos.visualizar`, `diagnosticos.editar`, etc.)
continua como evolução posterior.
