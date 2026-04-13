import logging
import json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from routers import facturas, proceso, config, logs, contactos, providers
from scheduler import start_scheduler
from middleware.metrics import RequestTimingMiddleware
from middleware.request_id import RequestIdMiddleware

app = FastAPI(title="Sync-bank API")


class JsonLogFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "request_id"):
            payload["request_id"] = record.request_id
        if hasattr(record, "nit"):
            payload["nit"] = record.nit
        if hasattr(record, "source"):
            payload["source"] = record.source
        if hasattr(record, "elapsed_ms"):
            payload["elapsed_ms"] = record.elapsed_ms
        return json.dumps(payload, ensure_ascii=True)


handler = logging.StreamHandler()
handler.setFormatter(JsonLogFormatter())
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
if not root_logger.handlers:
    root_logger.addHandler(handler)
else:
    root_logger.handlers = [handler]

app.add_middleware(RequestTimingMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None)
    logging.getLogger("api").exception("unhandled_error", extra={"request_id": request_id})
    return JSONResponse(
        status_code=500,
        content={
            "message": "Error interno del servidor",
            "code": "INTERNAL_ERROR",
            "request_id": request_id,
        },
    )

app.include_router(facturas.router, prefix="/api")
app.include_router(proceso.router, prefix="/api")
app.include_router(config.router, prefix="/api")
app.include_router(logs.router, prefix="/api")
app.include_router(contactos.router, prefix="/api")
app.include_router(providers.router, prefix="/api")

@app.on_event("startup")
async def startup_event():
    start_scheduler()

@app.get("/")
def read_root():
    return {"message": "Sync-bank API 🚀"}
