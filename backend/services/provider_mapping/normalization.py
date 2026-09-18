import re


def normalize_nit(value: str | None) -> str:
    return re.sub(r"\D", "", str(value or ""))
