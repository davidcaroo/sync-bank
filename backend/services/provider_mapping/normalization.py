import re


def normalize_nit(value: str | None) -> str:
    return re.sub(r"\D", "", str(value or ""))


def nit_key(value: str | None) -> str:
    """Digits of a NIT without its verification digit ("900741732-1" -> "900741732")."""
    return normalize_nit(re.sub(r"\s*-\s*\d\s*$", "", str(value or "")))
