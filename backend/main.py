import html
import logging
import json
import base64
import hmac
import hashlib
import secrets
import time
from urllib.parse import urlencode
from contextlib import asynccontextmanager
from pathlib import Path
import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from config import google_allowed_emails, settings
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

GOOGLE_PATHS = {"/login/google", "/login/google/callback"}
GOOGLE_STATE_COOKIE = "syncbank_oauth_state"
SESSION_COOKIE = "syncbank_session"
SESSION_SECONDS = 8 * 60 * 60


def _create_session(username: str | None = None) -> str:
    payload = f"{username or settings.ADMIN_USERNAME}:{int(time.time()) + SESSION_SECONDS}"
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
            (
                hmac.compare_digest(username, settings.ADMIN_USERNAME)
                or username.lower() in google_allowed_emails()
            )
            and int(expires) > time.time()
            and hmac.compare_digest(signature, expected)
        )
    except (ValueError, UnicodeDecodeError):
        return False


@app.middleware("http")
async def require_admin(request: Request, call_next):
    if request.url.path in {"/healthz", "/login", *GOOGLE_PATHS} or not settings.ADMIN_API_KEY:
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


LOGIN_TEMPLATE = (Path(__file__).parent / "login.html").read_text(encoding="utf-8")


GOOGLE_BUTTON = (
    '<a class="google" href="/login/google"><b>G</b>Continuar con Google</a>'
)


def _render_login(
    *, error: bool = False, username: str = "", message: str = "Credenciales incorrectas"
) -> str:
    alert = f'<div class="alert" role="alert">{html.escape(message)}</div>' if error else ""
    google = (
        GOOGLE_BUTTON
        if settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET
        else ""
    )
    return LOGIN_TEMPLATE.replace("{{GOOGLE}}", google).replace("{{ERROR}}", alert).replace(
        "{{USERNAME}}", html.escape(username, quote=True)
    )


@app.get("/login", response_class=HTMLResponse)
def login_page():
    return _render_login()


@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    if not (
        hmac.compare_digest(username, settings.ADMIN_USERNAME)
        and hmac.compare_digest(password, settings.ADMIN_API_KEY or "")
    ):
        return HTMLResponse(_render_login(error=True, username=username), status_code=401)
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


def _google_redirect_uri(request: Request) -> str:
    return settings.GOOGLE_REDIRECT_URI or str(request.url_for("google_callback"))


@app.get("/login/google")
def google_login(request: Request):
    if not (settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET):
        return RedirectResponse("/login")
    state = secrets.token_urlsafe(24)
    query = urlencode(
        {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": _google_redirect_uri(request),
            "response_type": "code",
            "scope": "openid email",
            "state": state,
            "prompt": "select_account",
            "login_hint": settings.IMAP_USER,
        }
    )
    response = RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{query}")
    response.set_cookie(
        GOOGLE_STATE_COOKIE,
        state,
        max_age=600,
        httponly=True,
        secure=settings.APP_ENV == "production",
        samesite="lax",
    )
    return response


@app.get("/login/google/callback", name="google_callback")
def google_callback(request: Request, code: str = "", state: str = ""):
    expected = request.cookies.get(GOOGLE_STATE_COOKIE, "")
    if not (code and state and expected and hmac.compare_digest(state, expected)):
        return _google_error("No se pudo iniciar sesion con Google", 401)
    try:
        token = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": _google_redirect_uri(request),
                "grant_type": "authorization_code",
            },
            timeout=10,
        )
        token.raise_for_status()
        # The id_token comes straight from Google's token endpoint over TLS, so
        # its claims are trusted without re-verifying the signature (OIDC 3.1.3.7).
        segment = token.json()["id_token"].split(".")[1]
        claims = json.loads(
            base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))
        )
    except (httpx.HTTPError, KeyError, IndexError, ValueError):
        return _google_error("No se pudo iniciar sesion con Google", 401)
    email = str(claims.get("email", "")).lower()
    if not claims.get("email_verified") or email not in google_allowed_emails():
        return _google_error("Ese correo no tiene acceso", 403)
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        SESSION_COOKIE,
        _create_session(email),
        max_age=SESSION_SECONDS,
        httponly=True,
        secure=settings.APP_ENV == "production",
        samesite="lax",
    )
    response.delete_cookie(GOOGLE_STATE_COOKIE)
    return response


def _google_error(message: str, status: int) -> HTMLResponse:
    return HTMLResponse(_render_login(error=True, message=message), status_code=status)


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
