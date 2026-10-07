"""Remove o usuario de teste da interface e os dados de exemplo. SOMENTE DEV/teste."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

from sqlalchemy import text
import seed_omni_demo
from app.config import settings
from app.database import PlatformSessionLocal, tenant_session
from app.models.platform_auth import PlatformTenant

EMAILS = ["e2e.revisor@exemplo-teste.com.br", "e2e.admin@exemplo-teste.com.br"]
if settings.app_env.strip().lower() not in ("development", "dev", "test", "local"):
    sys.exit("Recusado: so roda com APP_ENV de desenvolvimento/teste.")
db = PlatformSessionLocal()
demo = db.query(PlatformTenant).filter(PlatformTenant.codigo == "MDP_DEMO").first()
uids = [r[0] for r in db.execute(text("select id from usuarios where email = any(:e)"), {"e": EMAILS})]
with tenant_session(db, demo.id) as t:
    seed_omni_demo.remove(t)
    for uid in uids:
        t.execute(text("delete from usuarios_empresas where usuario_id in (select id from usuarios_tenant where platform_usuario_id=:u)"), {"u": str(uid)})
        t.execute(text("delete from usuarios_tenant where platform_usuario_id=:u"), {"u": str(uid)})
    t.commit()
for uid in uids:
    for sql in ("delete from sessoes_usuario where usuario_id=:u", "delete from usuarios_tenants where usuario_id=:u", "delete from usuarios where id=:u"):
        db.execute(text(sql), {"u": str(uid)})
db.commit()
print("removido.")
