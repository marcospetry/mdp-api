# MDP API 0.4.0 — Núcleo de autenticação

Evolução da 0.3.1 com autenticação central da plataforma MDP, mantendo os CRUDs existentes sem proteção nesta versão.

## Incluído
- Login por e-mail e senha com Argon2.
- JWT access token.
- Refresh token com hash no banco e rotação.
- Sessões revogáveis.
- MFA/TOTP obrigatório para superadmin.
- Segredo TOTP criptografado com Fernet.
- `/api/auth/login`, `/api/auth/mfa/setup`, `/api/auth/mfa/verify`, `/api/auth/refresh`, `/api/auth/logout`, `/api/auth/me`.
- Dependências `get_current_user`, `get_current_context` e `require_permission` preparadas para a 0.4.1.
- Script interativo `scripts/bootstrap_superadmin.py` para criar o primeiro superadmin sem senha em código ou migration.

## Importante
Os CRUDs de Diagnóstico/Contatos existentes continuam como na 0.3.1. A proteção por JWT, empresa ativa e permissões será aplicada na 0.4.1 após validar o núcleo Auth.

## Novas variáveis de ambiente
Consulte `.env.example`. Em especial, configure `SECRET_KEY` e `MFA_ENCRYPTION_KEY` antes de iniciar a API.
