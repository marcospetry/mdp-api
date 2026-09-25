BEGIN;
INSERT INTO papeis_plataforma(codigo,nome,descricao) VALUES ('SUPERADMIN','Superadministrador','Acesso administrativo total à plataforma MDP') ON CONFLICT (codigo) DO UPDATE SET nome=EXCLUDED.nome,descricao=EXCLUDED.descricao,ativo=true;
INSERT INTO tenants(id,codigo,nome,slug,ativo) VALUES ('c2f4e821-4894-4d67-ba38-0aedaaec3a39','MDP','MDP Consultoria','mdp',true) ON CONFLICT (id) DO UPDATE SET codigo=EXCLUDED.codigo,nome=EXCLUDED.nome,slug=EXCLUDED.slug,ativo=true;
INSERT INTO usuarios_papeis_plataforma(usuario_id,papel_id) SELECT '57c9793d-537d-4f2e-bdde-72c1b345586c'::uuid,id FROM papeis_plataforma WHERE codigo='SUPERADMIN' ON CONFLICT DO NOTHING;
INSERT INTO usuarios_tenants(usuario_id,tenant_id,ativo) VALUES ('57c9793d-537d-4f2e-bdde-72c1b345586c','c2f4e821-4894-4d67-ba38-0aedaaec3a39',true) ON CONFLICT (usuario_id,tenant_id) DO UPDATE SET ativo=true;
INSERT INTO funcionalidades(codigo,nome,ordem) VALUES
('EMPRESAS','Empresas',10),('FILIAIS','Filiais / Unidades',20),('AREAS','Áreas',30),('CONTATOS','Contatos',40),('ORIGENS','Origens de Contato',50),('TIPOS_INTERACAO','Tipos de Interação',60),('CATEGORIAS_DIAGNOSTICO','Categorias de Diagnóstico',70),('PERGUNTAS_DIAGNOSTICO','Perguntas de Diagnóstico',80),('FORMULARIOS','Formulários',90),('DIAGNOSTICOS','Diagnósticos',100),('CRM_OMNI','CRM Omni',110),('OMNI_LINKS','Omni Links',120)
ON CONFLICT (codigo) DO UPDATE SET nome=EXCLUDED.nome,ordem=EXCLUDED.ordem,ativo=true;
INSERT INTO tenants_funcionalidades(tenant_id,funcionalidade_id,ativo) SELECT 'c2f4e821-4894-4d67-ba38-0aedaaec3a39',id,true FROM funcionalidades ON CONFLICT (tenant_id,funcionalidade_id) DO UPDATE SET ativo=true,desabilitado_em=NULL;
COMMIT;
