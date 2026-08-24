# MDP API 0.5.0

Versão de adequação da API ao novo schema do Diagnóstico MDP.

## Pré-requisito

Banco com a Migration 003 do Diagnóstico aplicada.

## Principais mudanças

- suporte a `natureza`, `ideal`, `sugestao`;
- suporte a `estado_interno`;
- CRUD API de faixas numéricas;
- API de regras de exibição;
- endpoint de metadados;
- models alinhados também às tabelas de execução;
- todas as rotas administrativas do diagnóstico continuam protegidas por JWT/contexto;
- `POST /api/contatos` permanece público e não foi alterado.

Documentação completa: `MDP_API_Diagnostico_v0.5.0.md`.
