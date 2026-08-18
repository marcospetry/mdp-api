# MDP API - Comparativo 0.2.0 x pacote CRUD 0.3.0 x 0.3.1

## Base usada

A versão 0.3.1 foi reconstruída a partir da API original 0.2.0 fornecida pelo projeto.

## O que a versão CRUD 0.3.0 havia alterado

Comparação arquivo a arquivo mostrou que os arquivos existentes da API original foram preservados, com exceção de `app/main.py`, que registrava as novas rotas e atualizava a versão/CORS. Os CRUDs foram adicionados em quatro arquivos novos:

- `app/models/diagnostico.py`
- `app/schemas/diagnostico.py`
- `app/routers/diagnostico_catalogo.py`
- `app/routers/diagnostico_formularios.py`

O pacote 0.3.0 não continha `.env`. No teste local, a API utilizou um `.env` existente apontando para `localhost:5432`; depois do túnel, a conexão chegou ao PostgreSQL mas foi recusada por credencial incorreta. Esse problema de ambiente foi a causa do `Loading`/500 observado.

## Correções feitas na 0.3.1

1. Reconstrução sobre a API original 0.2.0.
2. Inclusão controlada dos quatro módulos de CRUD.
3. Registro das rotas em `app/main.py`.
4. Ajuste dos tamanhos de campos para refletir o PostgreSQL real:
   - categoria.nome = varchar(120)
   - pergunta.codigo = varchar(30)
   - pergunta.tipo_resposta = varchar(30)
   - pergunta.metodo_avaliacao = varchar(20)
   - opção.valor = varchar(80)
   - opção.rotulo = varchar(150)
5. Validação de peso de formulário como valor não negativo, alinhada ao CHECK da Migration 002.
6. Timeout de conexão PostgreSQL de 5 segundos, evitando espera indefinida quando host, porta ou credenciais estiverem incorretos.
7. Inclusão de `.env.example` sem credenciais reais.
8. Inclusão de smoke test PowerShell de leitura.

## Validações executadas

- Compilação de todos os módulos Python: OK.
- Importação da aplicação FastAPI 0.3.1: OK.
- Registro das rotas antigas e novas: OK.
- Teste de integração em banco temporário para o módulo de diagnóstico: OK.
- Fluxo validado no teste:
  - health
  - listar 8 categorias
  - listar 25 perguntas
  - localizar PF001
  - listar opções da PF001
  - criar formulário
  - associar PF001 e PF023
  - listar associações
  - reordenar perguntas
  - remover associação

## O que não foi alterado

- CRUD de contatos.
- Serviço de e-mail.
- Models de contato, empresa e interação.
- Configuração base do FastAPI, além das novas rotas/CORS e versão.
- Migration 002 já aplicada no banco.
- Pontuações das opções, que permanecem 0 nesta etapa.
- Autenticação/Migration 003, que não faz parte desta versão.
