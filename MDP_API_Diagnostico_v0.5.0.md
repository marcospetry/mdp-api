# MDP API — Diagnóstico v0.5.0

**Data:** 24/08/2026  
**Versão anterior:** 0.4.0  
**Versão:** 0.5.0  
**Pré-requisito de banco:** Migration `003_adequacao_diagnostico_v1` aplicada.

## 1. Objetivo da versão

A v0.5.0 alinha a API ao schema atual do Diagnóstico MDP e deixa a camada de **configuração/backoffice** pronta para a construção dos CRUDs administrativos de:

- categorias;
- perguntas;
- opções;
- faixas numéricas;
- formulários;
- associação formulário × pergunta;
- ordenação;
- regras de exibição;
- metadados dos domínios do diagnóstico.

A execução pública do diagnóstico, gravação de respostas por prospect, evidências, convite/token e motor final de achados permanecem como etapa posterior.

## 2. Banco esperado

### Tabelas de configuração

- `categorias_diagnostico`
- `perguntas_diagnostico`
- `opcoes_pergunta_diagnostico`
- `faixas_avaliacao_numero`
- `formularios_diagnostico`
- `formularios_perguntas`
- `regras_exibicao_perguntas`

### Tabelas de execução já mapeadas nos models

- `diagnosticos`
- `respostas_diagnostico`
- `respostas_diagnostico_opcoes`
- `evidencias_diagnostico`

A v0.5.0 já mantém os models SQLAlchemy alinhados a essas tabelas, mas ainda não publica endpoints de execução.

## 3. Novos campos suportados

### `perguntas_diagnostico`

- `natureza`
- `ideal`
- `sugestao`

### `opcoes_pergunta_diagnostico`

- `estado_interno`

### `respostas_diagnostico`

- `opcao_id`
- `estado_interno`

## 4. Domínios oficiais da v0.5.0

### Tipo de resposta

- `ESCOLHA_UNICA`
- `MULTIPLA_ESCOLHA`
- `NUMERO`
- `TEXTO_CURTO`

### Natureza

- `AVALIATIVA`
- `CONTEXTO`

### Estado interno

- `ALTO`
- `MEDIO`
- `BAIXO`
- `NA`
- `NAO_SEI`

A API expõe esses valores em:

`GET /api/diagnostico/metadados`

## 5. Segurança

Todas as rotas administrativas de `/api/diagnostico/*` usam:

`Depends(get_current_context)`

Portanto exigem:

- Bearer token válido;
- sessão válida e não revogada;
- usuário ativo;
- vínculo com a empresa quando aplicável, salvo superadmin.

A v0.5.0 **não torna nenhuma rota administrativa do diagnóstico pública**.

O endpoint público já utilizado pelo site permanece inalterado:

`POST /api/contatos`

### Permissões granulares

A infraestrutura existente possui `require_permission()`, porém não foram inventados novos códigos de permissão nesta versão. A v0.5.0 mantém o mesmo nível de proteção já adotado pelos CRUDs de diagnóstico da 0.4.0: autenticação obrigatória e contexto de empresa.

RBAC granular por ação poderá ser adicionado depois que os códigos oficiais de permissão dos CRUDs forem definidos.

## 6. Endpoints de categorias

- `GET /api/diagnostico/categorias`
- `POST /api/diagnostico/categorias`
- `GET /api/diagnostico/categorias/{categoria_id}`
- `PUT /api/diagnostico/categorias/{categoria_id}`
- `DELETE /api/diagnostico/categorias/{categoria_id}`

`DELETE` permanece como desativação lógica (`ativo=false`).

## 7. Endpoints de perguntas

- `GET /api/diagnostico/perguntas`
- `POST /api/diagnostico/perguntas`
- `GET /api/diagnostico/perguntas/{pergunta_id}`
- `PUT /api/diagnostico/perguntas/{pergunta_id}`
- `DELETE /api/diagnostico/perguntas/{pergunta_id}`

Novidades:

- filtro opcional por `natureza`;
- suporte a `natureza`, `ideal` e `sugestao`;
- detalhe da pergunta retorna opções e faixas;
- criação de pergunta pode receber opções/faixas no mesmo payload;
- validações de compatibilidade entre `tipo_resposta` e `natureza`.

## 8. Endpoints de opções

- `GET /api/diagnostico/perguntas/{pergunta_id}/opcoes`
- `POST /api/diagnostico/perguntas/{pergunta_id}/opcoes`
- `PUT /api/diagnostico/opcoes/{opcao_id}`
- `DELETE /api/diagnostico/opcoes/{opcao_id}`

Suporte novo:

- `estado_interno`.

Regras principais:

- pergunta `CONTEXTO` não aceita estado interno;
- `NUMERO` e `TEXTO_CURTO` não aceitam opções;
- `ESCOLHA_UNICA + AVALIATIVA` exige estado interno nas opções;
- banco impede repetição do mesmo estado na mesma pergunta.

## 9. Endpoints de faixas numéricas

Novos:

- `GET /api/diagnostico/perguntas/{pergunta_id}/faixas`
- `POST /api/diagnostico/perguntas/{pergunta_id}/faixas`
- `PUT /api/diagnostico/faixas/{faixa_id}`
- `DELETE /api/diagnostico/faixas/{faixa_id}`

Somente perguntas:

`NUMERO + AVALIATIVA`

podem possuir faixas.

A API e o banco validam limites e o banco também impede sobreposição de faixas.

## 10. Endpoints de formulários

Mantidos:

- `GET /api/diagnostico/formularios`
- `POST /api/diagnostico/formularios`
- `GET /api/diagnostico/formularios/{formulario_id}`
- `PUT /api/diagnostico/formularios/{formulario_id}`
- `DELETE /api/diagnostico/formularios/{formulario_id}`

A resposta detalhada agora inclui:

- perguntas associadas;
- natureza das perguntas;
- regras de exibição cadastradas.

## 11. Builder formulário × perguntas

Mantidos:

- `GET /api/diagnostico/formularios/{formulario_id}/perguntas`
- `POST /api/diagnostico/formularios/{formulario_id}/perguntas`
- `PUT /api/diagnostico/formularios/{formulario_id}/perguntas/{pergunta_id}`
- `DELETE /api/diagnostico/formularios/{formulario_id}/perguntas/{pergunta_id}`
- `PUT /api/diagnostico/formularios/{formulario_id}/perguntas/ordenacao`

Ao remover uma pergunta do formulário, regras de exibição daquele formulário que dependam dela são removidas antes da associação.

## 12. Endpoints de regras de exibição

Novos:

- `GET /api/diagnostico/formularios/{formulario_id}/regras-exibicao`
- `POST /api/diagnostico/formularios/{formulario_id}/regras-exibicao`
- `PUT /api/diagnostico/regras-exibicao/{regra_id}`
- `DELETE /api/diagnostico/regras-exibicao/{regra_id}`

Validações:

- pergunta origem e destino devem ser diferentes;
- opção deve pertencer à pergunta de origem;
- pergunta origem deve estar ativa no formulário;
- pergunta destino deve estar ativa no formulário;
- combinação duplicada é impedida pelo banco.

## 13. Arquivos alterados/criados

### Alterados

- `app/main.py`
- `app/models/diagnostico.py`
- `app/schemas/diagnostico.py`
- `app/routers/diagnostico_catalogo.py`
- `app/routers/diagnostico_formularios.py`

### Criados

- `app/routers/diagnostico_estrutura.py`
- `scripts/smoke_test_diagnostico_v050.py`
- `MDP_API_Diagnostico_v0.5.0.md`
- `README_0.5.0.md`

## 14. Compatibilidade com campos legados

A v0.5.0 **não remove**:

- `perguntas_diagnostico.peso`
- `perguntas_diagnostico.metodo_avaliacao`
- `perguntas_diagnostico.gera_achado`
- `opcoes_pergunta_diagnostico.pontuacao`
- `formularios_perguntas.peso`
- `diagnosticos.pontuacao_total`
- `diagnosticos.classificacao`
- `respostas_diagnostico.resposta_boolean`
- `respostas_diagnostico.pontuacao`

Eles permanecem por compatibilidade e não devem comandar o novo motor por estados.

## 15. Testes realizados antes do empacotamento

- compilação Python de toda a pasta `app`: OK;
- import isolado dos três routers do diagnóstico: OK;
- geração de OpenAPI isolada dos routers: OK;
- 33 operações administrativas do diagnóstico identificadas como protegidas por segurança: OK;
- registro do router novo no `main.py`: OK;
- versão do `main.py` alterada para `0.5.0`: OK.

O pacote também inclui um smoke test para ser executado no ambiente real após deploy.

## 16. Smoke test pós-deploy

Dentro do ambiente da API:

```bash
python scripts/smoke_test_diagnostico_v050.py
```

Também validar:

1. `GET /api/health` retorna `0.5.0`;
2. `POST /api/contatos` continua funcionando pelo formulário do site;
3. chamada sem Bearer para `/api/diagnostico/metadados` retorna `401`;
4. chamada autenticada para `/api/diagnostico/metadados` retorna os domínios;
5. Swagger/OpenAPI lista faixas e regras de exibição.

## 17. O que fica fora do escopo da v0.5.0

- convite/token para prospect;
- execução pública do formulário;
- endpoints de gravação das respostas pelo prospect;
- upload operacional de evidências;
- motor de avaliação/achados;
- achados cruzados;
- relatório final;
- regra definitiva de congelamento/versionamento de formulário já utilizado;
- RBAC granular por operação de CRUD.

## 18. Próximo passo

Após deploy e validação da v0.5.0, a API estará pronta para iniciar os CRUDs administrativos de manutenção do catálogo e formulários.

A etapa seguinte deve ser a interface administrativa:

**Categorias → Perguntas/Opções/Faixas → Formulários/Builder → Regras de Exibição.**
