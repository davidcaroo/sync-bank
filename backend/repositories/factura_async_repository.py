from __future__ import annotations

from typing import Any, Awaitable, Callable

from repositories.factura_repository import (
    get_factura_with_items,
    get_facturas_paginated,
    get_facturas_stats,
    get_successful_causacion,
    update_factura_fields,
    update_item_fields,
)
from services.factura_contracts import CausacionRepositoryPort, FacturaRepositoryPort
from services.supabase_service import save_causacion


class SyncFacturaRepositoryAdapter(FacturaRepositoryPort):
    def __init__(self, *, run_in_executor: Callable[[Callable[[], Any]], Awaitable[Any]]) -> None:
        self._run_in_executor = run_in_executor

    async def get_successful_causacion(self, factura_id: str) -> dict[str, Any] | None:
        return await self._run_in_executor(lambda: get_successful_causacion(factura_id))

    async def get_facturas_stats(self) -> list[dict[str, Any]]:
        rows = await self._run_in_executor(get_facturas_stats)
        return rows or []

    async def get_facturas_paginated(
        self,
        *,
        page: int,
        page_size: int,
        estado: str | None = None,
        proveedor: str | None = None,
        desde: str | None = None,
        hasta: str | None = None,
    ) -> Any:
        return await self._run_in_executor(
            lambda: get_facturas_paginated(
                page=page,
                page_size=page_size,
                estado=estado,
                proveedor=proveedor,
                desde=desde,
                hasta=hasta,
            )
        )

    async def get_factura_with_items(self, factura_id: str) -> dict[str, Any] | None:
        return await self._run_in_executor(lambda: get_factura_with_items(factura_id))

    async def update_factura_fields(self, factura_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        return await self._run_in_executor(lambda: update_factura_fields(factura_id, payload))

    async def update_item_fields(self, item_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        return await self._run_in_executor(lambda: update_item_fields(item_id, payload))


class SyncCausacionRepositoryAdapter(CausacionRepositoryPort):
    def __init__(self, *, run_in_executor: Callable[[Callable[[], Any]], Awaitable[Any]]) -> None:
        self._run_in_executor = run_in_executor

    async def save_causacion(self, payload: dict[str, Any]) -> None:
        await self._run_in_executor(lambda: save_causacion(payload))
