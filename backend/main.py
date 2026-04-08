from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import facturas, proceso, config, logs, contactos
from scheduler import start_scheduler

app = FastAPI(title="Sync-bank API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(facturas.router, prefix="/api")
app.include_router(proceso.router, prefix="/api")
app.include_router(config.router, prefix="/api")
app.include_router(logs.router, prefix="/api")
app.include_router(contactos.router, prefix="/api")

@app.on_event("startup")
async def startup_event():
    start_scheduler()

@app.get("/")
def read_root():
    return {"message": "Sync-bank API 🚀"}
