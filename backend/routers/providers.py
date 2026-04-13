from fastapi import APIRouter, HTTPException
from services.provider_mapping_service import provider_mapping_service
from security.admin_auth import verify_admin_key
from fastapi import Depends
from repositories.factura_repository import list_provider_nits
from repositories.db_utils import run_in_executor

router = APIRouter(prefix="/providers", tags=["providers"])


@router.post("/recompute", dependencies=[Depends(verify_admin_key)])
async def recompute_mapping(nit: str | None = None):
    """Recompute mapping for a single NIT or for all providers found in local invoices.
    If `nit` is provided, only that provider is processed.
    """
    if nit:
        res = await provider_mapping_service.compute_and_save_mapping(nit, None)
        if res:
            return {"ok": True, "result": res}
        raise HTTPException(status_code=404, detail="No mapping computed or not enough data")

    # No NIT provided: iterate distinct NITs from local facturas
    try:
        nits = await run_in_executor(lambda: list_provider_nits())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    results = []
    for n in nits:
        try:
            out = await provider_mapping_service.compute_and_save_mapping(n, None)
            results.append({"nit": n, "result": out})
        except Exception as exc:
            results.append({"nit": n, "error": str(exc)})

    return {"ok": True, "count": len(results), "results": results}
