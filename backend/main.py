import logging
import json
import base64
import hmac
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from config import settings
from observability.telemetry import init_telemetry
from routers import facturas, proceso, config, logs, contactos, providers
from scheduler import start_scheduler
from middleware.metrics import RequestTimingMiddleware
from middleware.request_id import RequestIdMiddleware
from repositories.database import close_pool, open_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    open_pool()
    init_telemetry()
    start_scheduler()
    try:
        yield
    finally:
        close_pool()


app = FastAPI(title="Sync-bank API", lifespan=lifespan)


@app.middleware("http")
async def require_admin(request: Request, call_next):
    if request.url.path == "/healthz" or not settings.ADMIN_API_KEY:
        return await call_next(request)
    authorization = request.headers.get("Authorization", "")
    try:
        scheme, encoded = authorization.split(" ", 1)
        username, password = base64.b64decode(encoded).decode().split(":", 1)
    except (ValueError, UnicodeDecodeError):
        scheme, username, password = "", "", ""
    valid = (
        scheme.lower() == "basic"
        and hmac.compare_digest(username, settings.ADMIN_USERNAME)
        and hmac.compare_digest(password, settings.ADMIN_API_KEY)
    )
    if not valid:
        return JSONResponse(
            status_code=401,
            content={"message": "Autenticacion requerida"},
            headers={"WWW-Authenticate": 'Basic realm="Sync-bank"'},
        )
    return await call_next(request)


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
        if hasattr(record, "job_id"):
            payload["job_id"] = record.job_id
        if hasattr(record, "factura_id"):
            payload["factura_id"] = record.factura_id
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


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None)
    logging.getLogger("api").exception(
        "unhandled_error", extra={"request_id": request_id}
    )
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


@app.get("/metrics")
def metrics():
    if not settings.METRICS_ENABLED:
        return JSONResponse(status_code=404, content={"message": "metrics disabled"})
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/healthz")
def healthcheck():
    return {"message": "Sync-bank API 🚀"}


static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
else:

    @app.get("/")
    def read_root():
        return {"message": "Sync-bank API 🚀"}
