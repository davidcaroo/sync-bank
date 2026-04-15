from __future__ import annotations

from typing import Any, Protocol


class FacturaRepositoryPort(Protocol):
    async def get_successful_causacion(self, factura_id: str) -> dict[str, Any] | None:
        ...

    async def get_facturas_stats(self) -> list[dict[str, Any]]:
        ...

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
        ...

    async def get_factura_with_items(self, factura_id: str) -> dict[str, Any] | None:
        ...

    async def update_factura_fields(self, factura_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        ...

    async def update_item_fields(self, item_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        ...


class CausacionRepositoryPort(Protocol):
    async def save_causacion(self, payload: dict[str, Any]) -> None:
        ...
