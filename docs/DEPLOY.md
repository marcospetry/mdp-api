# MDP Consultoria — Deploy e Infraestrutura

**Versão do documento:** 0.1  
**Data:** 12/08/2026  
**Status:** Estado atual confirmado

## 1. Ambiente

### VPS

- Provedor: Hostinger
- Sistema operacional: Ubuntu 24.04
- IPv4: `179.198.116.174`

### Plataforma

- Dokploy
- Docker
- Traefik

## 2. Serviços atualmente identificados

| Serviço | Container/Imagem | Porta |
|---|---|---|
| MDP API | `mdpsite-mdpapi-*` | 8000/tcp |
| PostgreSQL MDP | `mdpsite-mdppostgres-*` / postgres:17 | 5432/tcp |
| Site MDP | `site-*` | 80/tcp |
| Kanban App | `kanban-kanban-lph8ja-app-1` | 8501 -> 8000 |
| Kanban DB | `kanban-kanban-lph8ja-db-1` | 5432/tcp |
| Traefik | `dokploy-traefik` | 80/443 |
| Dokploy | `dokploy.*` | 3000 |
| PostgreSQL Dokploy | `dokploy-postgres.*` | 5432/tcp |

## 3. Domínio da API

Domínio:

`api.mdpconsultoria.com.br`

Destino DNS confirmado:

`179.198.116.174`

## 4. HTTPS

Proxy:

Traefik

Certificate Provider:

Let's Encrypt

Certificado confirmado em 12/08/2026:

```text
subject=CN = api.mdpconsultoria.com.br
issuer=C = US, O = Let's Encrypt, CN = YR1
notBefore=Aug 12 11:16:52 2026 GMT
notAfter=Nov 10 11:16:51 2026 GMT
```

Teste final:

```text
GET https://api.mdpconsultoria.com.br/docs
HTTP/1.1 200 OK
Server: uvicorn
```

## 5. Incidente DNS/SSL registrado

Durante a configuração inicial, o Let's Encrypt falhou porque o DNS ainda retornava NXDOMAIN.

Erro identificado no Traefik:

```text
DNS problem: NXDOMAIN looking up A for api.mdpconsultoria.com.br
DNS problem: NXDOMAIN looking up AAAA for api.mdpconsultoria.com.br
```

Após a propagação DNS:

```text
api.mdpconsultoria.com.br -> 179.198.116.174
```

o Traefik conseguiu obter um certificado válido.

## 6. Banco da MDP

Container identificado:

`mdpsite-mdppostgres-*`

Imagem:

`postgres:17`

Banco:

`mdp`

Usuário:

`mdp`

Porta interna:

`5432`

Credenciais não devem ser registradas neste documento.

## 7. Separação de bancos

Existem bancos PostgreSQL independentes para:

- MDP API;
- Kanban;
- Dokploy.

Eles não devem ser tratados como um único banco.

## 8. Aplicação local

Projeto conhecido em:

```text
D:\work\mdp-api
```

Arquivos principais:

```text
.env
.gitignore
.venv/
app/
Dockerfile
requirements.txt
```

## 9. Procedimento recomendado para futuras alterações

### Desenvolvimento

1. alterar localmente;
2. testar localmente;
3. validar banco/migration;
4. atualizar documentação;
5. versionar no Git;
6. publicar no Dokploy;
7. validar logs;
8. validar `/api/health`;
9. validar `/docs`;
10. executar teste funcional do recurso alterado.

### Produção

Evitar alterações manuais diretas em container em execução.

Preferir:

- código versionado;
- configuração declarada;
- migrations/scripts versionados;
- deploy reproduzível.

## 10. Comandos úteis de diagnóstico

Listar containers:

```bash
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Ports}}"
```

Localizar Traefik:

```bash
docker ps | grep traefik
```

Logs Traefik:

```bash
docker logs dokploy-traefik --tail 100
```

Ver certificado:

```bash
echo | openssl s_client -connect api.mdpconsultoria.com.br:443 -servername api.mdpconsultoria.com.br 2>/dev/null | openssl x509 -noout -issuer -subject -dates
```

Ver resolução DNS na VPS:

```bash
getent hosts api.mdpconsultoria.com.br
```

## 11. Pontos ainda a documentar

- processo exato de build/deploy da MDP API no Dokploy;
- origem Git/repositório;
- estratégia de rollback;
- backups do PostgreSQL;
- política de retenção;
- variáveis de ambiente necessárias;
- healthcheck do container;
- logs e observabilidade;
- procedimento de migration;
- processo de deploy do site;
- processo de deploy do Kanban.
