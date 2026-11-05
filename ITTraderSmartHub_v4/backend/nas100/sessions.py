"""Trading-session classification using IANA time zones (DST-correct).

Each session is a LOCAL wall-clock window in its own zone, evaluated on weekdays
(Mon-Fri, by local date). UTC offsets are never hard-coded, so the UK/US daylight
saving mismatch weeks (US switches earlier in spring and later in autumn) are
handled by the zone rules.

DEFAULT CONVENTIONS (configurable; they are conventions, not exchange rules)
    asia          09:00-18:00 Asia/Tokyo
    london        08:00-16:30 Europe/London
    new_york      08:00-17:00 America/New_York        (FX-style NY session)
    ny_cash       09:30-16:00 America/New_York        (US cash equity hours)
    ny_open       first `ny_open_minutes` (default 60) of ny_cash
    overlap       london AND new_york simultaneously

Windows are half-open [start, end). Input must be timezone-aware.
"""
from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from typing import Dict, Tuple

from .tz import get_zone

Window = Tuple[str, time, time]   # (IANA zone, start, end)

DEFAULT_WINDOWS: Dict[str, Window] = {
    'asia': ('Asia/Tokyo', time(9, 0), time(18, 0)),
    'london': ('Europe/London', time(8, 0), time(16, 30)),
    'new_york': ('America/New_York', time(8, 0), time(17, 0)),
    'ny_cash': ('America/New_York', time(9, 30), time(16, 0)),
}


@dataclass(frozen=True)
class SessionState:
    asia: bool
    london: bool
    new_york: bool
    ny_cash: bool
    ny_open: bool
    overlap: bool

    def active(self):
        names = [n for n in ('asia', 'london', 'new_york') if getattr(self, n)]
        return tuple(names)


def _in_window(ts_utc: datetime, window: Window) -> bool:
    zone, start, end = window
    local = ts_utc.astimezone(get_zone(zone))
    if local.weekday() >= 5:
        return False
    return start <= local.time() < end


def session_state(ts: datetime, windows: Dict[str, Window] = None,
                  ny_open_minutes: int = 60) -> SessionState:
    if ts.tzinfo is None:
        raise ValueError('timestamp must be timezone-aware')
    w = dict(DEFAULT_WINDOWS)
    if windows:
        w.update(windows)
    ts = ts.astimezone(timezone.utc)
    asia, london = _in_window(ts, w['asia']), _in_window(ts, w['london'])
    ny, cash = _in_window(ts, w['new_york']), _in_window(ts, w['ny_cash'])
    ny_open = False
    if cash:
        zone, start, _ = w['ny_cash']
        local = ts.astimezone(get_zone(zone))
        minutes = (local.hour * 60 + local.minute) - (start.hour * 60 + start.minute)
        ny_open = 0 <= minutes < ny_open_minutes
    return SessionState(asia, london, ny, cash, ny_open, london and ny)
