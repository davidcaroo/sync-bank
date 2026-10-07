import asyncio
import logging

import httpx

from config import settings
from services.alegra_service import alegra_service
from services.notifier import notify
from services.timezone_service import now_bogota

logger = logging.getLogger("advance_service")

MAX_BILL_PAGES = 5
_lock = asyncio.Lock()
_pending: asyncio.Task | None = None


def _today() -> str:
    return now_bogota().date().isoformat()


def _nits() -> list[str]:
    return [n.strip() for n in settings.AUTO_ADVANCE_NITS.split(",") if n.strip()]


def _amount(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(round(float(value), 2))


def plan_allocations(bills: list[dict], advances: list[dict]) -> tuple[list[dict], list[dict]]:
    """Pay open bills oldest first from the advances' available balance (oldest advance
    first). A bill is paid whole or not at all, and the first one that does not fit stops
    the plan so bills are never paid out of order."""
    pools = [
        {"idGlobal": a["idGlobal"], "left": float(a["amountAvailable"])}
        for a in sorted(advances, key=lambda a: (a.get("date") or "", a["idGlobal"]))
        if float(a.get("amountAvailable") or 0) > 0
    ]
    plan: list[dict] = []
    shortfall: list[dict] = []
    for b in sorted(bills, key=lambda b: (b["date"], int(b["id"]))):
        need = float(b["balance"])
        number = (b.get("numberTemplate") or {}).get("fullNumber") or b["id"]
        if shortfall or sum(p["left"] for p in pools) + 1e-9 < need:
            shortfall.append({"id": b["id"], "number": number, "balance": need})
            continue
        allocations = []
        for pool in pools:
            take = min(pool["left"], need)
            if take > 0:
                allocations.append({"idGlobal": pool["idGlobal"], "amount": take})
                pool["left"] -= take
                need -= take
            if need <= 1e-9:
                break
        plan.append({"id": b["id"], "number": number, "balance": float(b["balance"]), "allocations": allocations})
    return plan, shortfall


async def _json(response):
    payload = response.json()
    return payload.get("data", []) if isinstance(payload, dict) else payload


async def _open_bills(client, provider_id: str) -> list[dict]:
    found: list[dict] = []
    for page in range(MAX_BILL_PAGES):
        response = await client.get(
            f"{alegra_service.base_url}/bills",
            params={
                "start": page * 30,
                "limit": 30,
                "client_id": provider_id,
                "order_field": "date",
                "order_direction": "DESC",
            },
            headers=alegra_service.headers,
        )
        bills = await _json(response) if response.status_code == 200 else []
        for b in bills:
            if b["date"] < settings.MIN_ISSUE_DATE:
                return found
            if b.get("status") == "open" and float(b.get("balance") or 0) > 0:
                found.append(b)
        if len(bills) < 30:
            break
    return found


async def _advances(client, provider_id: str) -> list[dict]:
    response = await client.get(
        f"{alegra_service.base_url}/advances-applied",
        params={"client_id": provider_id, "currency": "COP", "type": "out"},
        headers=alegra_service.headers,
    )
    return await _json(response) if response.status_code == 200 else []


async def _apply(client, item: dict) -> str | None:
    body = {
        "advances": [
            {
                "idGlobal": a["idGlobal"],
                "amount": _amount(a["amount"]),
                "date": _today(),
                "journal": {"numberTemplate": {"id": settings.ADVANCE_NUMBER_TEMPLATE_ID}},
            }
            for a in item["allocations"]
        ]
    }
    response = await client.post(
        f"{alegra_service.base_url}/bills/{item['id']}/advances-applied",
        json=body,
        headers=alegra_service.headers,
    )
    if response.status_code != 200:
        return f"HTTP {response.status_code}: {response.text[:200]}"
    check = await client.get(f"{alegra_service.base_url}/bills/{item['id']}", headers=alegra_service.headers)
    paid = check.json() if check.status_code == 200 else {}
    if float(paid.get("balance") or 0) > 0:
        return f"Alegra respondio OK pero la factura sigue con saldo {paid.get('balance')}"
    return None


async def _run_provider(client, nit: str, dry_run: bool, summary: dict) -> None:
    provider = await alegra_service.find_provider_contact_by_nit(client, nit)
    if not provider:
        summary["errors"].append({"nit": nit, "error": "proveedor no encontrado en Alegra"})
        return
    provider_id = str(provider["id"])
    bills = await _open_bills(client, provider_id)
    if not bills:
        return
    advances = await _advances(client, provider_id)
    plan, shortfall = plan_allocations(bills, advances)

    for item in plan:
        if dry_run:
            summary["applied"].append({**item, "simulated": True})
            continue
        error = await _apply(client, item)
        if error:
            summary["errors"].append({"nit": nit, "number": item["number"], "error": error})
            await notify(
                f"anticipo-error:{item['id']}",
                "No se pudo aplicar el anticipo a una factura",
                f"Factura {item['number']} (NIT {nit}): {error}\n\nAplica el anticipo a mano en Alegra.",
            )
            return
        summary["applied"].append(item)

    if shortfall:
        summary["shortfall"].extend(shortfall)
        if not dry_run:
            needed = sum(s["balance"] for s in shortfall)
            available = sum(float(a["amountAvailable"]) for a in advances)
            await notify(
                "anticipo-insuficiente",
                "El anticipo no alcanza para pagar las facturas",
                f"Hay {len(shortfall)} facturas del NIT {nit} sin pagar por {_amount(needed)} "
                f"y el saldo de anticipos disponible es {_amount(available)}.\n\n"
                "Registra una recarga (anticipo a terceros) en Alegra y se aplicara sola.",
            )


async def run(*, dry_run: bool) -> dict:
    """Pay the open bills of the configured providers with their advance balance."""
    summary: dict = {"dry_run": dry_run, "applied": [], "shortfall": [], "errors": []}
    async with _lock:
        if not _nits():
            return summary
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            for nit in _nits():
                try:
                    await _run_provider(client, nit, dry_run, summary)
                except Exception as exc:
                    logger.exception("advance_run_failed", extra={"nit": nit})
                    summary["errors"].append({"nit": nit, "error": str(exc)})
    return summary


async def run_scheduled() -> None:
    mode = settings.AUTO_ADVANCE_MODE
    if mode not in {"on", "dry_run"}:
        return
    summary = await run(dry_run=mode != "on")
    logger.info(
        "advance_run",
        extra={"source": mode, "job_id": f"{len(summary['applied'])}/{len(summary['shortfall'])}"},
    )


def request_run() -> None:
    """Right after a causation: run now unless one is already queued or running."""
    global _pending
    if settings.AUTO_ADVANCE_MODE != "on" or (_pending and not _pending.done()):
        return
    _pending = asyncio.get_running_loop().create_task(run_scheduled())
