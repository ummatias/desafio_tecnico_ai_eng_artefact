"""O "agora" da loja: `REFERENCE_DATE` (data e hora no fuso da loja) ou o relógio real."""

from datetime import datetime
from zoneinfo import ZoneInfo

from emporio.config import Settings


def store_now(settings: Settings) -> datetime:
    tz = ZoneInfo(settings.store_tz)
    ref = settings.reference_date
    if ref is None:
        return datetime.now(tz)
    return ref.replace(tzinfo=tz) if ref.tzinfo is None else ref.astimezone(tz)
