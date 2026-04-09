from datetime import datetime
from zoneinfo import ZoneInfo


BOGOTA_TZ = ZoneInfo("America/Bogota")


def now_bogota() -> datetime:
    return datetime.now(BOGOTA_TZ)


def to_bogota(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=BOGOTA_TZ)
    return dt.astimezone(BOGOTA_TZ)
