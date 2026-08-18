# MDP API 0.3.1 - CRUDs do Diagnóstico

Base: API original 0.2.0 fornecida pelo projeto, preservando contatos, e-mail, configuração e deploy.

## O que foi incorporado

- CRUD de categorias do diagnóstico.
- CRUD de perguntas.
- CRUD de opções de resposta.
- CRUD de formulários.
- Associação N:N formulário x perguntas.
- Alteração de ordem, peso, obrigatoriedade e status da associação.
- Rotas de diagnóstico registradas em `app/main.py`.

## Correções em relação ao pacote 0.3.0 anterior

- Modelos e schemas ajustados aos tamanhos reais do PostgreSQL:
  - categoria.nome: 120
  - pergunta.codigo: 30
  - pergunta.tipo_resposta: 30
  - pergunta.metodo_avaliacao: 20
  - opção.valor: 80
  - opção.rotulo: 150
- Peso de associação de formulário validado como >= 0, conforme Migration 002.
- Timeout de conexão PostgreSQL de 5 segundos para evitar requisição presa indefinidamente em `Loading` quando a conexão estiver incorreta.
- `.env` real não é empacotado. Use o `.env` do ambiente funcional ou copie `.env.example` e configure corretamente.

## Importante sobre banco local x VPS

A API não deve assumir `localhost:5432` quando o PostgreSQL estiver na VPS.
Para teste local com túnel SSH, a `DATABASE_URL` deve apontar para a porta local do túnel, por exemplo `localhost:15432`, usando o usuário e senha reais do PostgreSQL MDP.

## Teste rápido

Com a API rodando:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\smoke_test.ps1
```

O teste é somente leitura e valida:

- health 0.3.1
- 8 categorias
- 25 perguntas
- PF001 existente
- 3 opções da PF001
- Sim / Parcialmente / Não

A Migration 002 deve estar aplicada antes dos testes de formulários.
