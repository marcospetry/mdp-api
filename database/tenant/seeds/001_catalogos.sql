-- 001_catalogos.sql  (seed de catalogos de um tenant NOVO; idempotente)
-- Copia dos INSERTs das migrations tenant 003 e 004, sem tocar em dados da MDP.
BEGIN;

INSERT INTO tipos_organizacao (codigo,nome,descricao,ordem,padrao_sistema,ativo) VALUES
('CLIENTE','Cliente','Organização cliente da organização principal do Tenant.',1,TRUE,TRUE),
('FORNECEDOR','Fornecedor','Organização fornecedora de produtos ou serviços.',2,TRUE,TRUE),
('TERCEIRO','Terceiro','Organização terceira relacionada à operação.',3,TRUE,TRUE),
('ORGAO_EXTERNO','Órgão Externo','Órgão externo relacionado à operação.',4,TRUE,TRUE),
('BANCO','Banco','Instituição bancária ou financeira relacionada.',5,TRUE,TRUE),
('PARCEIRO','Parceiro','Organização parceira.',6,TRUE,TRUE)
ON CONFLICT (codigo) DO UPDATE SET nome=EXCLUDED.nome, descricao=EXCLUDED.descricao, padrao_sistema=TRUE;

INSERT INTO origens_contato (codigo, nome, ordem, padrao_sistema) VALUES
 ('SITE','Site',1,true),('ADMIN','Cadastro manual',2,true),('WHATSAPP','WhatsApp',3,true),
 ('INSTAGRAM','Instagram',4,true),('EMAIL','E-mail',5,true),('TELEFONE','Telefone',6,true),
 ('VISITA_PRESENCIAL','Visita presencial',7,true),('INDICACAO','Indicação',8,true),('GOOGLE','Google',9,true),
 ('EVENTO','Evento',10,true),('META_ADS','Meta Ads',11,true),('GOOGLE_ADS','Google Ads',12,true),
 ('PARCERIA','Parceria',13,true),('PROSPECCAO_ATIVA','Prospecção ativa',14,true),('OUTRO','Outro',15,true),
 ('OMNI','Omni',16,true)
ON CONFLICT DO NOTHING;

INSERT INTO tipos_interacao (codigo, nome, ordem, padrao_sistema) VALUES
 ('FORMULARIO_SITE','Formulário do site',1,true),('WHATSAPP_MENSAGEM','WhatsApp - Mensagem',2,true),
 ('INSTAGRAM_DIRECT','Instagram - Direct',3,true),('INSTAGRAM_COMENTARIO','Instagram - Comentário',4,true),
 ('EMAIL','E-mail',5,true),('LIGACAO','Ligação',6,true),('VISITA','Visita',7,true),('REUNIAO','Reunião',8,true),
 ('ANOTACAO_INTERNA','Anotação interna',9,true),('OUTRO','Outro',10,true),('OMNI_AGENDAMENTO','Omni - Agendamento',11,true)
ON CONFLICT DO NOTHING;

INSERT INTO tipos_unidade (codigo, nome, ordem, padrao_sistema) VALUES
 ('MATRIZ','Matriz',1,true),('FILIAL','Filial',2,true),('ESCRITORIO','Escritório',3,true),('LOJA','Loja',4,true),
 ('QUIOSQUE','Quiosque',5,true),('FABRICA','Fábrica',6,true),('DISTRIBUIDORA','Distribuidora',7,true),
 ('CENTRO_DISTRIBUICAO','Centro de Distribuição',8,true),('DEPOSITO','Depósito',9,true),
 ('POSTO_ATENDIMENTO','Posto de Atendimento',10,true),('HOME_OFFICE','Home Office',11,true),('OUTRO','Outro',12,true)
ON CONFLICT DO NOTHING;

COMMIT;
