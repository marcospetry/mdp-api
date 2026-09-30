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
Base = declarative_base()

platform_database_url = _database_url(settings.database_url, settings.platform_database_name)
# A conexão PLATAFORMA é a única conexão fixa. Bancos operacionais são
# resolvidos após validar o TENANT da sessão.
from contextlib import contextmanager
from functools import lru_cache
from fastapi import Depends, HTTPException
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

def _engine(url: str):
    return create_engine(url, pool_pre_ping=True,
                         connect_args={"connect_timeout": 5} if make_url(url).drivername.startswith("postgresql+") else {})


platform_engine = _engine(platform_database_url)
PlatformSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=platform_engine)


@lru_cache(maxsize=64)
def _tenant_session_factory(url: str):
    return sessionmaker(autocommit=False, autoflush=False, bind=_engine(url))


def tenant_connection_url(platform_db: Session, tenant_id):
    # Importação local evita ciclo de importação com os models.
    from app.models.platform_auth import PlatformTenant, PlatformTenantDatabase
    row = platform_db.query(PlatformTenantDatabase).join(
        PlatformTenant, PlatformTenant.id == PlatformTenantDatabase.tenant_id
    ).filter(PlatformTenant.id == tenant_id, PlatformTenant.ativo.is_(True),
             PlatformTenantDatabase.ativo.is_(True)).first()
    if row is None:
        raise HTTPException(status_code=503, detail="Banco do TENANT não configurado ou inativo.")
    # DATABASE_URL fornece o host/usuário/senha específicos do ambiente.
    # Para infra MDP_SHARED, o cadastro determina o nome físico do banco.
    # Infra externa/dedicada requer implementação explícita de secret_ref.
    if row.tipo_infra != "MDP_SHARED":
        raise HTTPException(status_code=503, detail="Infraestrutura do TENANT ainda não suportada.")
    if not row.database_name or '/' in row.database_name:
        raise HTTPException(status_code=503, detail="Nome de banco inválido.")
    return make_url(_psycopg_url(settings.database_url)).set(database=row.database_name)


@contextmanager
def tenant_session(platform_db: Session, tenant_id):
    factory = _tenant_session_factory(tenant_connection_url(platform_db, tenant_id))
    db = factory()
    try:
        yield db
    finally:
        db.close()


def get_platform_db():
    db = PlatformSessionLocal()
    try:
        yield db
    finally:
        db.close()


