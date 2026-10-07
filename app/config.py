from datetime import timedelta
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    platform_database_name: str = "mdp_platform"
    default_tenant_database_name: str = "tenant_mdp"
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

    meta_whatsapp_verify_token: str = "change-me"
    meta_whatsapp_app_secret: str = "change-me"
    meta_whatsapp_access_token: str = "change-me"
    meta_whatsapp_phone_number_id: str = "1230708946787093"

    # Desenvolvimento local: bypass explícito de autenticação.
    # Seguro por padrão: só fica efetivo quando APP_ENV=development E DEV_AUTH_BYPASS=true.
    # --- Omni / Meta (Instagram). Tudo desligado por padrao: OMNI_META_ENABLED=false ---
    omni_meta_enabled: bool = False
    omni_public_base_url: str = "https://api.mdpconsultoria.com.br"
    omni_connection_encryption_key: str | None = None
    instagram_app_id: str | None = None
    instagram_app_secret: str | None = None
    instagram_webhook_verify_token: str | None = None
    meta_graph_version: str = "v25.0"

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
