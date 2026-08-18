from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.contatos import router as contatos_router
from app.routers.diagnostico_catalogo import router as diagnostico_catalogo_router
from app.routers.diagnostico_formularios import router as diagnostico_formularios_router


app = FastAPI(
    title="MDP API",
    version="0.3.1",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://mdpconsultoria.com.br",
        "https://www.mdpconsultoria.com.br",
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
app.include_router(diagnostico_catalogo_router)
app.include_router(diagnostico_formularios_router)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "mdp-api",
        "version": "0.3.1",
    }
