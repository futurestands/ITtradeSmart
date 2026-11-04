"""Isolated, synthetic-only observation ledger for SmartHub risk research.

No Flask route, device input, network, terminal or order-execution code is wired
here. In particular, writing a row NEVER attests a live broker account.

An append-only SQLite event history is useful for deterministic replay, but is
not by itself an authenticated MT5 history or protection against DB tampering.
"""
from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path

from compliance_engine import AccountModel, DataOrigin

_ALIAS = re.compile(r"[a-z][a-z0-9_-]{2,31}\Z")
_MAX_EVENTS = 1_000_000


class EventKind(str, Enum):
    SNAPSHOT = "SNAPSHOT"
    CLOSED_BALANCE = "CLOSED_BALANCE"
    END_OF_DAY_BALANCE = "END_OF_DAY_BALANCE"


@dataclass(frozen=True)
class ObservationEvent:
    alias: str
    model: AccountModel
    kind: EventKind
    observed_at_utc: datetime
    session_start_utc: datetime
    initial_capital: Decimal
    balance: Decimal
    equity: Decimal
    day_start_balance: Decimal
    reset_offset_minutes: int
    observation_offset_minutes: int
    origin: DataOrigin = DataOrigin.SYNTHETIC_TEST
    currency: str = "USD"


@dataclass(frozen=True)
class ObservationSummary:
    alias: str
    model: AccountModel
    count: int
    latest: ObservationEvent
    highest_recorded_eod_balance: Decimal | None
    highest_recorded_closed_balance: Decimal | None
    live_verified: bool = False
    history_complete: bool = False
    execution_authorized: bool = False


def _utc(dt: object) -> bool:
    return (isinstance(dt, datetime) and dt.tzinfo is not None
            and dt.utcoffset() == timedelta(0))


def _money(x: object) -> bool:
    return (type(x) is Decimal and x.is_finite()
            and (x.is_zero() or -12 <= x.adjusted() <= 11))


def _validate(event: ObservationEvent) -> None:
    if type(event) is not ObservationEvent:
        raise ValueError("INVALID_EVENT")
    if not isinstance(event.alias, str) or not _ALIAS.fullmatch(event.alias):
        raise ValueError("INVALID_ALIAS")
    if type(event.model) is not AccountModel or type(event.kind) is not EventKind:
        raise ValueError("INVALID_MODEL_OR_KIND")
    if type(event.origin) is not DataOrigin or event.origin is not DataOrigin.SYNTHETIC_TEST:
        raise ValueError("BROKER_ADAPTER_NOT_IMPLEMENTED")
    if event.currency != "USD":
        raise ValueError("UNSUPPORTED_CURRENCY")
    nums = (event.initial_capital, event.balance, event.equity, event.day_start_balance)
    if any(not _money(x) for x in nums) or event.initial_capital <= 0 or event.day_start_balance <= 0:
        raise ValueError("INVALID_MONEY_DATA")
    if not _utc(event.observed_at_utc) or not _utc(event.session_start_utc):
        raise ValueError("INVALID_UTC_TIME")
    if event.observed_at_utc < event.session_start_utc:
        raise ValueError("INVALID_SESSION_TIME")
    if (event.observed_at_utc - event.session_start_utc) >= timedelta(hours=25):
        raise ValueError("SESSION_RESET_UNVERIFIED")
    from compliance_engine import POLICIES
    offset_allowlist = POLICIES[event.model].reset_offsets_minutes
    if (type(event.reset_offset_minutes) is not int or type(event.observation_offset_minutes) is not int
            or event.reset_offset_minutes not in offset_allowlist
            or event.observation_offset_minutes not in offset_allowlist):
        raise ValueError("INVALID_SERVER_TIME_OFFSET")
    start_local = event.session_start_utc + timedelta(minutes=event.reset_offset_minutes)
    current_local = event.observed_at_utc + timedelta(minutes=event.observation_offset_minutes)
    if ((start_local.hour, start_local.minute, start_local.second, start_local.microsecond) != (0, 0, 0, 0)
            or start_local.date() != current_local.date()):
        raise ValueError("SESSION_RESET_UNVERIFIED")


def _stored(event: ObservationEvent) -> tuple:
    return (
        event.alias, event.model.value, event.kind.value,
        event.observed_at_utc.isoformat(), event.session_start_utc.isoformat(),
        *(str(x) for x in (event.initial_capital, event.balance, event.equity, event.day_start_balance)),
        event.reset_offset_minutes, event.observation_offset_minutes,
        event.origin.value, event.currency,
    )


def _unpack(row: tuple) -> ObservationEvent:
    return ObservationEvent(
        alias=row[0], model=AccountModel(row[1]), kind=EventKind(row[2]),
        observed_at_utc=datetime.fromisoformat(row[3]),
        session_start_utc=datetime.fromisoformat(row[4]),
        initial_capital=Decimal(row[5]), balance=Decimal(row[6]),
        equity=Decimal(row[7]), day_start_balance=Decimal(row[8]),
        reset_offset_minutes=row[9], observation_offset_minutes=row[10],
        origin=DataOrigin(row[11]), currency=row[12],
    )


class ObservationLedger:
    """Use a separately chosen local DB. Never pass the production Gateway DB.

    This prototype contains *no* real trusted writer. The public append method
    rejects all broker-origin claims and records only SYNTHETIC_TEST observations.
    High-water summaries are observed maxima, not a certified complete history.
    """

    def __init__(self, database_path: str | Path):
        if not isinstance(database_path, (str, Path)) or not str(database_path).strip():
            raise ValueError("EXPLICIT_DB_PATH_REQUIRED")
        self.path = Path(database_path)
        if (self.path.is_symlink() or self.path.parent.is_symlink()
                or not self.path.parent.is_dir()):
            raise ValueError("UNSAFE_DB_LOCATION")
        with closing(self._connect()) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS observation_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alias TEXT NOT NULL,
                model TEXT NOT NULL,
                kind TEXT NOT NULL,
                observed_at_utc TEXT NOT NULL,
                session_start_utc TEXT NOT NULL,
                initial_capital TEXT NOT NULL,
                balance TEXT NOT NULL,
                equity TEXT NOT NULL,
                day_start_balance TEXT NOT NULL,
                reset_offset_minutes INTEGER NOT NULL,
                observation_offset_minutes INTEGER NOT NULL,
                origin TEXT NOT NULL CHECK(origin = 'SYNTHETIC_TEST'),
                currency TEXT NOT NULL CHECK(currency = 'USD'),
                UNIQUE(alias, observed_at_utc)
            )""")
            db.execute("""CREATE INDEX IF NOT EXISTS idx_observation_alias
                           ON observation_events(alias, id)""")
            db.execute("""CREATE TRIGGER IF NOT EXISTS observation_no_update
                           BEFORE UPDATE ON observation_events
                           BEGIN SELECT RAISE(ABORT, 'APPEND_ONLY'); END""")
            db.execute("""CREATE TRIGGER IF NOT EXISTS observation_no_delete
                           BEFORE DELETE ON observation_events
                           BEGIN SELECT RAISE(ABORT, 'APPEND_ONLY'); END""")

    def _connect(self):
        if self.path.is_symlink():
            raise ValueError("UNSAFE_DB_LOCATION")
        db = sqlite3.connect(self.path, timeout=10.0)
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def append(self, event: ObservationEvent) -> int:
        _validate(event)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            last = db.execute("""SELECT id, model, initial_capital, observed_at_utc
                                 FROM observation_events WHERE alias=?
                                 ORDER BY id DESC LIMIT 1""", (event.alias,)).fetchone()
            if last:
                if last[1] != event.model.value or Decimal(last[2]) != event.initial_capital:
                    raise ValueError("PROFILE_MODEL_OR_INITIAL_BALANCE_CHANGED")
                if event.observed_at_utc <= datetime.fromisoformat(last[3]):
                    raise ValueError("NON_MONOTONIC_OBSERVATION")
                prior = db.execute("""SELECT session_start_utc, day_start_balance,
                    reset_offset_minutes FROM observation_events WHERE id=?""", (last[0],)).fetchone()
                previous_session = datetime.fromisoformat(prior[0])
                if event.session_start_utc < previous_session:
                    raise ValueError("NON_MONOTONIC_SESSION")
                if event.session_start_utc == previous_session and (
                    event.day_start_balance != Decimal(prior[1])
                    or event.reset_offset_minutes != prior[2]
                ):
                    raise ValueError("SESSION_BASELINE_CHANGED")
            cnt = db.execute("SELECT COUNT(*) FROM observation_events WHERE alias=?", (event.alias,)).fetchone()[0]
            if cnt >= _MAX_EVENTS:
                raise ValueError("PROFILE_EVENT_LIMIT_REACHED")
            cur = db.execute("""INSERT INTO observation_events (
                alias, model, kind, observed_at_utc, session_start_utc,
                initial_capital, balance, equity, day_start_balance,
                reset_offset_minutes, observation_offset_minutes, origin, currency)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", _stored(event))
            return int(cur.lastrowid)

    def summary(self, alias: str) -> ObservationSummary | None:
        if not isinstance(alias, str) or not _ALIAS.fullmatch(alias):
            raise ValueError("INVALID_ALIAS")
        with closing(self._connect()) as db, db:
            cursor = db.execute("""SELECT alias,model,kind,observed_at_utc,
                session_start_utc,initial_capital,balance,equity,day_start_balance,
                reset_offset_minutes,observation_offset_minutes,origin,currency
                FROM observation_events WHERE alias=? ORDER BY id ASC""", (alias,))
            count = 0
            latest = None
            maximum_eod = None
            maximum_closed = None
            for row in cursor:
                event = _unpack(row)
                count += 1
                latest = event
                if event.kind is EventKind.END_OF_DAY_BALANCE:
                    maximum_eod = event.balance if maximum_eod is None else max(maximum_eod, event.balance)
                elif event.kind is EventKind.CLOSED_BALANCE:
                    maximum_closed = event.balance if maximum_closed is None else max(maximum_closed, event.balance)
        if latest is None:
            return None
        return ObservationSummary(
            alias=alias, model=latest.model, count=count, latest=latest,
            highest_recorded_eod_balance=maximum_eod,
            highest_recorded_closed_balance=maximum_closed,
        )
