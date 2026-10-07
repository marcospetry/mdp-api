"""Prepara o teste de interface: cria o usuario de teste e os dados de exemplo no tenant MDP_DEMO.
SOMENTE DEV/teste (trava por APP_ENV). Use cleanup_ui_test.py para remover tudo depois."""
import sys
from pathlib import Path
from uuid import uuid4
from datetime import timedelta

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

from sqlalchemy import text
import seed_omni_demo
from app.config import settings
from app.database import PlatformSessionLocal, tenant_session
from app.models.auth import UsuarioEmpresa, UsuarioTenantLocal
from app.models.empresa import Empresa
from app.models.platform_auth import PlatformTenant, PlatformUsuario, PlatformUsuarioTenant
from app.security.password import hash_password
from app.services.auth_service import utcnow

EMAIL, SENHA = "e2e.revisor@exemplo-teste.com.br", "SenhaE2E#12345"

if settings.app_env.strip().lower() not in ("development", "dev", "test", "local"):
    sys.exit("Recusado: so roda com APP_ENV de desenvolvimento/teste.")

db = PlatformSessionLocal()
demo = db.query(PlatformTenant).filter(PlatformTenant.codigo == "MDP_DEMO").first()
if not demo:
    sys.exit("Tenant MDP_DEMO nao encontrado.")
u = db.query(PlatformUsuario).filter(PlatformUsuario.email == EMAIL).first()
if not u:
    u = PlatformUsuario(nome="E2E Revisor", email=EMAIL, password_hash=hash_password(SENHA), mfa_dispensado=True,
                        acesso_expira_em=utcnow() + timedelta(days=5))
    db.add(u); db.flush()
    db.add(PlatformUsuarioTenant(id=uuid4(), usuario_id=u.id, tenant_id=demo.id, ativo=True)); db.commit()
    with tenant_session(db, demo.id) as t:
        emp = t.query(Empresa).first()
        op = t.execute(text("select id from perfis where codigo='OMNI_OPERADOR'")).scalar()
        loc = UsuarioTenantLocal(platform_usuario_id=u.id, ativo=True); t.add(loc); t.flush()
        t.add(UsuarioEmpresa(usuario_id=loc.id, empresa_id=emp.id, perfil_id=op, ativo=True, acesso_todas_unidades=True, acesso_todas_areas=True))
        t.commit()
with tenant_session(db, demo.id) as t:
    seed_omni_demo.remove(t)
    print("dados de exemplo:", seed_omni_demo.seed(t))
    # texto malicioso de terceiro: o teste confere que aparece como TEXTO e nunca vira HTML
    t.execute(text("update omni_mensagens set texto='<img src=x onerror=window.__xss=1> hello' where external_message_id='sample-ig-2-m1'"))
    t.commit()
print("pronto. usuario:", EMAIL)
