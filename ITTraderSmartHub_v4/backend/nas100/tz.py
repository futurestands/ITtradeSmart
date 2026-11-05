"""Time-zone lookup with an actionable error for hosts lacking an IANA database
(notably Windows, where `pip install tzdata` is required for `zoneinfo`)."""
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def get_zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise RuntimeError(
            f'Time zone {name!r} not found. On Windows install the IANA database: '
            f'pip install tzdata (see backend/nas100/requirements-nas100.txt)') from exc
