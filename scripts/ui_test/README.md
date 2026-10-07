# Teste de interface do Omni (opcional)

Simula um navegador (jsdom) contra a API REAL: login em ingles, abas, Integrations, Inbox, Comments, idioma,
protecao contra HTML de terceiros e sign out. 27 verificacoes. SOMENTE em DEV.

Requisitos: Node 18+ (`node --version`). Uma vez: `npm install jsdom` (dentro desta pasta).

Passo a passo (3 janelas do CMD, na raiz do projeto, com o .venv ativo):
1. `python scripts\ui_test\setup_ui_test.py`     (cria o usuario de teste e os dados de exemplo)
2. Em outra janela, suba a API como de costume (porta 8000) e, na pasta scripts\ui_test: `node ui.test.js`
   (outra porta: `set BASE_URL=http://127.0.0.1:PORTA` antes do node)
3. `python scripts\ui_test\cleanup_ui_test.py`   (remove tudo)

Esperado: `Resumo: 27 ok, 0 falha(s)`.

Teste das telas do Instagram (conectar, volta do Instagram, estados do canal, comentarios, erros de envio; a Meta e simulada):
`node instagram_flow.test.js`  -> esperado `Resumo: 25 ok, 0 falha(s)`.

**Rode `setup_ui_test.py` ANTES de cada teste**: ele recria os dados de exemplo (abrir uma conversa a marca como lida, e isso muda o resultado do teste seguinte).

Teste da passagem de sessao do backoffice para o /omni (usuario so-Omni vai direto para /omni; ADMIN nao e redirecionado):
`node handoff.test.js`  -> esperado `Resumo: 10 ok, 0 falha(s)`. O setup agora cria tambem o usuario `e2e.admin@...` e o cleanup remove os dois.
Nao use em producao: o setup recusa APP_ENV diferente de development/test.
