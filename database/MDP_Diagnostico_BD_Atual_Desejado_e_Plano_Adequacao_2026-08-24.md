# MDP Diagnóstico — Situação Atual do Banco, Situação Desejada e Plano de Adequação

**Data:** 24/08/2026  
**Banco:** PostgreSQL 17  
**Database:** `mdp`

## 1. Premissas

- Os dados atuais de categorias, perguntas, opções e formulário são massa de teste.
- Não existem diagnósticos, respostas ou evidências reais.
- O objetivo é preservar a estrutura existente quando possível e adicionar apenas o necessário.
- Campos legados de pontuação não serão removidos agora, para evitar quebrar a API antes da análise técnica.

## 2. Situação atual

Tabelas principais já existentes:
- `categorias_diagnostico`
- `perguntas_diagnostico`
- `opcoes_pergunta_diagnostico`
- `formularios_diagnostico`
- `formularios_perguntas`
- `diagnosticos`
- `respostas_diagnostico`
- `evidencias_diagnostico`
- `empresas`
- `contatos`

Volume atual:
- 8 categorias
- 25 perguntas
- 90 opções
- 1 formulário
- 0 associações formulário/pergunta
- 0 diagnósticos
- 0 respostas
- 0 evidências

## 3. Gap por tabela

### `categorias_diagnostico`
Estrutura atual suficiente. O ajuste é de conteúdo/taxonomia, não de schema.

### `perguntas_diagnostico`
Existem:
`id, empresa_id, categoria_id, pergunta, tipo_resposta, peso, ordem, obrigatoria, ativo, created_at, updated_at, codigo, metodo_avaliacao, ajuda, gera_achado`

Adicionar:
- `natureza`
- `ideal`
- `sugestao`

Valores de `natureza`:
- `AVALIATIVA`
- `CONTEXTO`

Campos legados a manter por enquanto:
- `peso`
- `metodo_avaliacao`
- `gera_achado`

### `opcoes_pergunta_diagnostico`
Existem:
`id, pergunta_id, valor, rotulo, pontuacao, ordem, ativo, created_at, updated_at`

Adicionar:
- `estado_interno`

Valores:
- `ALTO`
- `MEDIO`
- `BAIXO`
- `NA`
- `NAO_SEI`

`estado_interno` deve ser `NULL` em perguntas de contexto.

Campo legado:
- `pontuacao`

### `formularios_diagnostico`
Estrutura atual já atende:
`id, empresa_id, codigo, nome, descricao, tipo, versao, ativo, created_at, updated_at`

Já existe:
- `CHECK (versao > 0)`
- `UNIQUE (empresa_id, codigo, versao)`

Pendência funcional: definir se editar formulário já utilizado cria nova versão.

### `formularios_perguntas`
Estrutura atual suficiente:
`id, formulario_id, pergunta_id, ordem, obrigatoria, peso, ativo, created_at, updated_at`

Já existe:
- `UNIQUE (formulario_id, pergunta_id)`
- `CHECK (peso >= 0)`

`peso` fica como legado por enquanto.

### `diagnosticos`
Estrutura atual:
`id, empresa_id, nome_contato, email_contato, telefone_contato, empresa_avaliada, status, pontuacao_total, classificacao, iniciado_em, concluido_em, created_at, updated_at, contato_id, formulario_id`

FKs:
- `empresa_id -> empresas.id`
- `contato_id -> contatos.id`
- `formulario_id -> formularios_diagnostico.id`

Campos legados:
- `pontuacao_total`
- `classificacao`

Pendência de modelagem:
- decidir futuramente se `empresa_avaliada` continuará como snapshot textual ou se será criada entidade própria.

### `respostas_diagnostico`
Estrutura atual:
`id, diagnostico_id, pergunta_id, resposta_texto, resposta_numero, resposta_boolean, pontuacao, observacao, created_at, updated_at`

Já existe:
- `UNIQUE (diagnostico_id, pergunta_id)`

Adicionar:
- `opcao_id`
- `estado_interno`

Campos legados:
- `resposta_boolean`
- `pontuacao`

### `evidencias_diagnostico`
Estrutura atual suficiente:
`id, empresa_id, diagnostico_id, resposta_id, tipo, arquivo_url, descricao, created_at, updated_at`

## 4. Novas tabelas necessárias

### `faixas_avaliacao_numero`
Para perguntas `NUMERO + AVALIATIVA`.

Campos:
- `id`
- `pergunta_id`
- `valor_min`
- `valor_max`
- `estado_interno`
- `created_at`
- `updated_at`

### `regras_exibicao_perguntas`
Para formulário adaptativo.

Campos:
- `id`
- `formulario_id`
- `pergunta_origem_id`
- `opcao_origem_id`
- `pergunta_destino_id`
- `created_at`
- `updated_at`

### `respostas_diagnostico_opcoes`
Para `MULTIPLA_ESCOLHA`.

Campos:
- `resposta_id`
- `opcao_id`
- `created_at`

## 5. Regras estruturais desejadas

Tipos de resposta válidos:
- `ESCOLHA_UNICA`
- `MULTIPLA_ESCOLHA`
- `NUMERO`
- `TEXTO_CURTO`

Regras:
1. `MULTIPLA_ESCOLHA` é sempre `CONTEXTO`.
2. `TEXTO_CURTO` é sempre `CONTEXTO`.
3. Pergunta `CONTEXTO` não aceita `estado_interno` nas opções.
4. `NUMERO` e `TEXTO_CURTO` não usam `opcoes_pergunta_diagnostico`.
5. Uma pergunta não pode ter o mesmo `estado_interno` duas vezes.
6. Perguntas `NUMERO + AVALIATIVA` usam faixas.
7. Faixas da mesma pergunta não podem se sobrepor.
8. Pergunta de origem e destino de regra devem pertencer ao formulário.
9. `opcao_origem_id` deve pertencer a `pergunta_origem_id`.
10. A resposta deve preservar `estado_interno` no momento da execução.

## 6. Taxonomia

Banco atual, considerado massa de teste:
1. Presença Física e Integração Digital
2. Presença Digital
3. Dados e Sistemas
4. Processos
5. Automação
6. Inteligência Artificial
7. Marketing e Divulgação
8. Reputação e Canais Externos

Modelo conceitual atual:
1. Presença Física e Experiência no Local
2. Google e Encontrabilidade
3. Site e Experiência Web
4. Redes Sociais
5. WhatsApp
6. E-mail e Formulários
7. Canais e Omnicanalidade
8. Dados e Sistemas
9. Processos de Atendimento e Interação
10. Automação e IA
11. Pós-Atendimento e Continuidade

A carga definitiva das categorias deverá ser feita depois da migration estrutural.

## 7. Campos legados que NÃO serão removidos agora

- `perguntas_diagnostico.peso`
- `perguntas_diagnostico.metodo_avaliacao`
- `perguntas_diagnostico.gera_achado`
- `opcoes_pergunta_diagnostico.pontuacao`
- `formularios_perguntas.peso`
- `diagnosticos.pontuacao_total`
- `diagnosticos.classificacao`
- `respostas_diagnostico.resposta_boolean`
- `respostas_diagnostico.pontuacao`

A remoção, depreciação ou manutenção deles só será decidida após análise da API.

## 8. Alterações necessárias

### Alterar
`perguntas_diagnostico`
- adicionar `natureza`
- adicionar `ideal`
- adicionar `sugestao`

`opcoes_pergunta_diagnostico`
- adicionar `estado_interno`

`respostas_diagnostico`
- adicionar `opcao_id`
- adicionar `estado_interno`
- adicionar FK de `opcao_id`

### Criar
- `faixas_avaliacao_numero`
- `regras_exibicao_perguntas`
- `respostas_diagnostico_opcoes`

## 9. O que não precisa ser alterado agora

- `categorias_diagnostico`
- `formularios_diagnostico`
- `formularios_perguntas`
- `evidencias_diagnostico`
- `empresas`
- `contatos`

## 10. Ordem recomendada

1. Backup do banco.
2. Aplicar migration estrutural.
3. Validar colunas, tabelas, constraints e triggers.
4. Analisar models SQLAlchemy.
5. Analisar schemas Pydantic.
6. Analisar endpoints atuais.
7. Adequar API.
8. Criar/adequar CRUDs.
9. Carregar taxonomia definitiva.
10. Carregar catálogo real.
11. Montar formulário real.
12. Implementar motor de avaliação.
13. Testar diagnóstico ponta a ponta.

## 11. Observação sobre DDL x DML

As alterações de estrutura são tecnicamente **DDL**, não DML.

Esta etapa usa principalmente:
- `ALTER TABLE`
- `CREATE TABLE`
- `CREATE INDEX`
- `CREATE FUNCTION`
- `CREATE TRIGGER`

DML (`INSERT`, `UPDATE`, `DELETE`) será usado depois para carregar categorias, perguntas, opções e formulários reais.
