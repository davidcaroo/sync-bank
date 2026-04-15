from __future__ import annotations

from typing import Any, Protocol


class FacturaRepositoryPort(Protocol):
    async def find_by_cufe(self, cufe: str | None) -> dict[str, Any] | None:
        ...

    async def save_factura(self, factura_payload: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
        ...


class ProviderConfigRepositoryPort(Protocol):
    async def get_config_cuenta(self, nit_proveedor: str | None) -> dict[str, Any] | None:
        ...

    async def sync_proveedor_nombre(self, nit_proveedor: str | None, nombre_proveedor: str | None) -> None:
        ...
