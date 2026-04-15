from __future__ import annotations

from typing import Any, Awaitable, Callable

from services.ingestion.contracts import FacturaRepositoryPort, ProviderConfigRepositoryPort


class SyncFacturaRepositoryAdapter(FacturaRepositoryPort):
    def __init__(
        self,
        *,
        run_in_executor: Callable[[Callable[[], Any]], Awaitable[Any]],
        find_factura_by_cufe: Callable[[str | None], dict[str, Any] | None],
        save_factura: Callable[[dict[str, Any], list[dict[str, Any]]], dict[str, Any]],
    ) -> None:
        self._run_in_executor = run_in_executor
        self._find_factura_by_cufe = find_factura_by_cufe
        self._save_factura = save_factura

    async def find_by_cufe(self, cufe: str | None) -> dict[str, Any] | None:
        return await self._run_in_executor(lambda: self._find_factura_by_cufe(cufe))

    async def save_factura(self, factura_payload: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
        return await self._run_in_executor(lambda: self._save_factura(factura_payload, items))


class SyncProviderConfigRepositoryAdapter(ProviderConfigRepositoryPort):
    def __init__(
        self,
        *,
        run_in_executor: Callable[[Callable[[], Any]], Awaitable[Any]],
        get_config_cuenta: Callable[[str | None], dict[str, Any] | None],
        sync_config_proveedor_nombre: Callable[[str | None, str | None], None],
    ) -> None:
        self._run_in_executor = run_in_executor
        self._get_config_cuenta = get_config_cuenta
        self._sync_config_proveedor_nombre = sync_config_proveedor_nombre

    async def get_config_cuenta(self, nit_proveedor: str | None) -> dict[str, Any] | None:
        return await self._run_in_executor(lambda: self._get_config_cuenta(nit_proveedor))

    async def sync_proveedor_nombre(self, nit_proveedor: str | None, nombre_proveedor: str | None) -> None:
        await self._run_in_executor(lambda: self._sync_config_proveedor_nombre(nit_proveedor, nombre_proveedor))
