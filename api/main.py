from fastapi import FastAPI
from api.routers import unfaelle, metadata, regionen, map

app = FastAPI(
    title="DBW Unfall-API",
    version="1.0.0"
)

app.include_router(unfaelle.router)
app.include_router(metadata.router)
app.include_router(regionen.router)


@app.get("/")
def root():
    return {"message": "API läuft"}