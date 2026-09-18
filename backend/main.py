import logging
import json
import base64
import hmac
import hashlib
import time
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from config import settings
from observability.telemetry import init_telemetry
from routers import facturas, proceso, config, logs, contactos, providers
from scheduler import start_scheduler
from middleware.metrics import RequestTimingMiddleware
from middleware.request_id import RequestIdMiddleware
from repositories.database import close_pool, open_pool
from repositories.schema_upgrades import apply_schema_upgrades


@asynccontextmanager
async def lifespan(app: FastAPI):
    open_pool()
    apply_schema_upgrades()
    init_telemetry()
    start_scheduler()
    try:
        yield
    finally:
        close_pool()


app = FastAPI(title="Sync-bank API", lifespan=lifespan)

SESSION_COOKIE = "syncbank_session"
SESSION_SECONDS = 8 * 60 * 60


def _create_session() -> str:
    payload = f"{settings.ADMIN_USERNAME}:{int(time.time()) + SESSION_SECONDS}"
    signature = hmac.new(
        settings.ADMIN_API_KEY.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}:{signature}".encode()).decode()


def _valid_session(token: str | None) -> bool:
    if not token or not settings.ADMIN_API_KEY:
        return False
    try:
        username, expires, signature = (
            base64.urlsafe_b64decode(token).decode().split(":")
        )
        payload = f"{username}:{expires}"
        expected = hmac.new(
            settings.ADMIN_API_KEY.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()
        return (
            hmac.compare_digest(username, settings.ADMIN_USERNAME)
            and int(expires) > time.time()
            and hmac.compare_digest(signature, expected)
        )
    except (ValueError, UnicodeDecodeError):
        return False


@app.middleware("http")
async def require_admin(request: Request, call_next):
    if request.url.path in {"/healthz", "/login"} or not settings.ADMIN_API_KEY:
        return await call_next(request)
    authorization = request.headers.get("Authorization", "")
    try:
        scheme, encoded = authorization.split(" ", 1)
        username, password = base64.b64decode(encoded).decode().split(":", 1)
    except (ValueError, UnicodeDecodeError):
        scheme, username, password = "", "", ""
    valid_basic = (
        scheme.lower() == "basic"
        and hmac.compare_digest(username, settings.ADMIN_USERNAME)
        and hmac.compare_digest(password, settings.ADMIN_API_KEY)
    )
    valid_cookie = _valid_session(request.cookies.get(SESSION_COOKIE))
    if not (valid_basic or valid_cookie):
        if not request.url.path.startswith(("/api/", "/metrics")):
            return RedirectResponse("/login")
        return JSONResponse(
            status_code=401,
            content={"message": "Autenticacion requerida"},
        )
    return await call_next(request)


LOGIN_PAGE = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Sync-bank</title>
<style>body{margin:0;background:#07111f;color:#e8eef7;font:16px system-ui;display:grid;place-items:center;min-height:100vh}form{width:min(360px,calc(100% - 48px));background:#101d2d;padding:32px;border:1px solid #26394f;border-radius:14px;box-shadow:0 24px 70px #0008}h1{margin:0 0 8px}p{color:#9fb0c5;margin:0 0 24px}label{display:block;margin:16px 0 6px}input,button{box-sizing:border-box;width:100%;padding:12px;border-radius:8px;font:inherit}input{border:1px solid #38506b;background:#07111f;color:white}button{margin-top:22px;border:0;background:#2f6fed;color:white;font-weight:700;cursor:pointer}.error{color:#ff9b9b;margin-top:14px}</style></head><body><form method="post"><h1>Sync-bank</h1><p>Acceso administrativo</p><label>Usuario</label><input name="username" autocomplete="username" required><label>Contraseña</label><input name="password" type="password" autocomplete="current-password" required><button>Ingresar</button>{error}</form></body></html>"""


@app.get("/login", response_class=HTMLResponse)
def login_page():
    return LOGIN_PAGE.replace("{error}", "")


@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    if not (
        hmac.compare_digest(username, settings.ADMIN_USERNAME)
        and hmac.compare_digest(password, settings.ADMIN_API_KEY or "")
    ):
        return HTMLResponse(
            LOGIN_PAGE.replace(
                "{error}", '<div class="error">Credenciales incorrectas</div>'
            ),
            status_code=401,
        )
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        SESSION_COOKIE,
        _create_session(),
        max_age=SESSION_SECONDS,
        httponly=True,
        secure=settings.APP_ENV == "production",
        samesite="lax",
    )
    return response


@app.post("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


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
