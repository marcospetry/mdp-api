from datetime import timedelta
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    preauth_token_minutes: int = 5
    max_login_attempts: int = 5
    login_lockout_minutes: int = 15
    mfa_encryption_key: str | None = None
    mfa_issuer: str = "MDP Consultoria"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    contato_destino: str | None = None

    # Desenvolvimento local: bypass explícito de autenticação.
    # Seguro por padrão: só fica efetivo quando APP_ENV=development E DEV_AUTH_BYPASS=true.
    app_env: str = "production"
    dev_auth_bypass: bool = False
    dev_auth_empresa_slug: str = "mdp"
    dev_auth_usuario_email: str | None = None

    @property
    def dev_auth_enabled(self) -> bool:
        return self.app_env.strip().lower() == "development" and self.dev_auth_bypass

    @property
    def login_lockout_delta(self):
        return timedelta(minutes=self.login_lockout_minutes)

    class Config:
        env_file = ".env"


settings = Settings()
