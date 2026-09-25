from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings


def _psycopg_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def _database_url(base_url: str, database_name: str) -> str:
    """Preserva host/porta/credenciais e troca somente o nome do banco."""
    parsed = urlsplit(_psycopg_url(base_url))
    return urlunsplit((parsed.scheme, parsed.netloc, f"/{database_name}", parsed.query, parsed.fragment))


# DATABASE_URL continua sendo a URL-base do ambiente. Nesta fase local ela ainda
# pode apontar para /mdp; os nomes físicos novos são definidos separadamente.
platform_database_url = _database_url(settings.database_url, settings.platform_database_name)
tenant_database_url = _database_url(settings.database_url, settings.default_tenant_database_name)


def _engine(url: str):
    return create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5} if url.startswith("postgresql+") else {},
    )


platform_engine = _engine(platform_database_url)
tenant_engine = _engine(tenant_database_url)

PlatformSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=platform_engine)
TenantSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=tenant_engine)

# Base continua única para os models declarativos. As sessões determinam em qual
# banco cada consulta é executada; não usamos Base.metadata.create_all().
Base = declarative_base()


def get_platform_db():
    db = PlatformSessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_tenant_db():
    """Banco operacional do Tenant padrão desta primeira etapa (tenant_mdp)."""
    db = TenantSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Compatibilidade temporária: os CRUDs existentes continuam importando get_db,
# mas passam a operar no banco operacional tenant_mdp.
def get_db():
    yield from get_tenant_db()
