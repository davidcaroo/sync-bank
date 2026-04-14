from __future__ import annotations


# Modes:
# - compras: prefer "IVA desc ... por compras"
# - servicios: prefer "IVA desc ... por servicios"
# - auto: infer from item description
PROVIDER_TAX_MODE_BY_NIT: dict[str, str] = {
    # Add your fixed NIT rules here.
    # "900123456": "compras",
    # "800987654": "servicios",
}


SUPERMARKET_HINTS = (
    "ara",
    "d1",
    "exito",
    "almacenes exito",
    "megatiendas",
    "supermercado",
)


def resolve_provider_tax_mode(nit: str | None, provider_name: str | None) -> str:
    normalized_nit = "".join(ch for ch in str(nit or "") if ch.isdigit())
    if normalized_nit and normalized_nit in PROVIDER_TAX_MODE_BY_NIT:
        mode = (PROVIDER_TAX_MODE_BY_NIT.get(normalized_nit) or "").strip().lower()
        if mode in {"compras", "servicios", "auto"}:
            return mode

    normalized_name = (provider_name or "").strip().lower()
    if any(hint in normalized_name for hint in SUPERMARKET_HINTS):
        return "compras"

    return "auto"
