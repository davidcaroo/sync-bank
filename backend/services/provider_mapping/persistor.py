from repositories.config_repository import save_config_cuenta
from repositories.db_utils import run_in_executor


class MappingPersistor:
    async def save_mapping(
        self,
        *,
        nit_proveedor: str,
        nombre_proveedor: str | None,
        cuenta: str,
        share: float,
        source: str,
    ) -> dict | None:
        return await run_in_executor(lambda: save_config_cuenta(
            nit_proveedor=nit_proveedor,
            nombre_proveedor=nombre_proveedor,
            id_cuenta_alegra=cuenta,
            id_centro_costo_alegra=None,
            confianza=round(share, 3),
            activo=True,
            source=source,
        ))
