from app.routers.platform_usuarios import router as platform_usuarios_router
from app.routers.platform_tipos_endpoint import router as platform_tipos_endpoint_router
from app.routers.platform_integracoes import router as platform_integracoes_router
from app.routers.platform_funcionalidades import router as platform_funcionalidades_router
from app.routers.platform_tenants import router as platform_tenants_router
from app.routers.platform_tenant_endpoints import router as platform_tenant_endpoints_router
from app.routers.whatsapp_webhook import router as whatsapp_webhook_router
from app.routers.admin_manutencao import router as admin_manutencao_router
from app.routers.admin_tipos_organizacao import router as admin_tipos_organizacao_router
from app.routers.admin_organizacao import router as admin_organizacao_router
from app.routers.admin_empresas_contatos import router as admin_empresas_contatos_router
from app.routers.diagnostico_estrutura import router as diagnostico_estrutura_router
from app.routers.diagnostico_formularios import router as diagnostico_formularios_router
from app.routers.diagnostico_catalogo import router as diagnostico_catalogo_router
from app.routers.diagnostico_aplicacoes import router as diagnostico_aplicacoes_router
from app.routers.diagnostico_publico import router as diagnostico_publico_router
from app.routers.auth import router as auth_router
from app.routers.contatos import router as contatos_router
from app import logging_filters
from app.routers.meta_instagram_webhook import router as meta_instagram_webhook_router
from app.routers.omni import router as omni_router
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


app = FastAPI(
    title="MDP API",
    version="0.5.0",
)

logging_filters.install()


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://mdpconsultoria.com.br",
        "https://www.mdpconsultoria.com.br",
        "https://admin.mdpconsultoria.com.br",
        "https://diagnostico.mdpconsultoria.com.br",
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(contatos_router)
app.include_router(auth_router)
app.include_router(omni_router)
app.include_router(meta_instagram_webhook_router)
app.include_router(diagnostico_catalogo_router)
app.include_router(diagnostico_formularios_router)
app.include_router(diagnostico_estrutura_router)
app.include_router(diagnostico_aplicacoes_router)
app.include_router(diagnostico_publico_router)
app.include_router(admin_empresas_contatos_router)
app.include_router(admin_organizacao_router)
app.include_router(admin_manutencao_router)
app.include_router(admin_tipos_organizacao_router)
app.include_router(whatsapp_webhook_router)
app.include_router(platform_tenants_router)
app.include_router(platform_funcionalidades_router)
app.include_router(platform_tenant_endpoints_router)
app.include_router(platform_tipos_endpoint_router)
app.include_router(platform_integracoes_router)
app.include_router(platform_usuarios_router)


STATIC_ADMIN_DIR = Path(__file__).resolve().parent / "static" / "admin"
STATIC_PUBLIC_DIR = Path(__file__).resolve().parent / "static" / "public"
STATIC_OMNI_DIR = Path(__file__).resolve().parent / "static" / "omni"
app.mount(
    "/admin-assets",
    StaticFiles(directory=STATIC_ADMIN_DIR),
    name="admin-assets",
)


app.mount(
    "/omni-assets",
    StaticFiles(directory=STATIC_OMNI_DIR),
    name="omni-assets",
)


@app.get("/omni", include_in_schema=False)
def omni_page():
    return FileResponse(STATIC_OMNI_DIR / "index.html")


@app.get("/login", include_in_schema=False)
def login_page():
    return FileResponse(STATIC_ADMIN_DIR / "index.html")


@app.get("/admin", include_in_schema=False)
def admin_page():
    return FileResponse(STATIC_ADMIN_DIR / "index.html")


@app.get("/diagnostico/responder/{token}", include_in_schema=False)
def diagnostico_publico_page(token: str):
    return FileResponse(STATIC_PUBLIC_DIR / "diagnostico.html")


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "mdp-api",
        "version": "0.5.0",
    }
