from fastapi import FastAPI


app = FastAPI(
    title="MDP API",
    version="0.1.0",
)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "mdp-api",
        "version": "0.1.0",
    }
