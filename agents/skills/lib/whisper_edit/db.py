"""Guarded database access + low-level conventions for the split/combine engine.

This module is the single safety choke point for opening MacWhisper's
`main.sqlite` (see `specs/macwhisper-database.md` §1 "Safety contract" and §9
"Write path"). It also owns the conventions every other module depends on:

- the BLOB-UUID <-> hex <-> canonical-uuid projections (§3.1),
- the dual time model (UTC-string `dateCreated` vs Mac-absolute-time
  `dateDeleted`, §3.2), and
- schema-drift column resolution via `PRAGMA table_info` (§8) — including the
  `modelIdentifer` typo and `playbackDuration` vs `duration`.

The dangerous boundaries (is-MacWhisper-running, wall-clock) are injected as
`ProcessChecker` / `Clock` protocols so the engine is unit-testable without a
live database or a running app (see the colocated tests). The read path uses a
read-only SQLite URI; the write path refuses to open while MacWhisper is
running and force-checkpoints the WAL so `main.sqlite` is self-contained before
anyone backs it up or writes to it.

Stdlib-only and 3.9-compatible, matching the sibling `lib/whisper/` package.
"""

from __future__ import annotations

import sqlite3
import subprocess
import uuid as _uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Mapping

# Seconds between the Unix epoch and the Mac "absolute time" epoch
# (2001-01-01 UTC). `dateDeleted` is stored as Mac absolute time (§3.2).
MAC_ABSOLUTE_EPOCH_OFFSET = 978307200.0

# Default app-support locations (§2). Callers may override for backups/tests.
DEFAULT_DB_PATH = (
    Path.home()
    / "Library/Application Support/MacWhisper/Database/main.sqlite"
)
EXTERNAL_MEDIA_DIRNAME = "ExternalMedia"

# Process-name fragments that indicate MacWhisper (or a helper) is alive.
DEFAULT_PROCESS_PATTERN = "macwhisper"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class WhisperEditError(Exception):
    """Base class for every error raised by the split/combine engine."""


class MacWhisperRunningError(WhisperEditError):
    """Raised when a read-write open is attempted while MacWhisper is alive.

    Writing to `main.sqlite` while the app holds it risks corrupting MacWhisper's
    state, so this is a hard, non-bypassable precondition (§1).
    """


class SchemaError(WhisperEditError):
    """Raised when the live schema lacks a column/table the engine requires."""


# ---------------------------------------------------------------------------
# Injected boundaries: process detection + wall clock
# ---------------------------------------------------------------------------


class ProcessChecker:
    """Structural type: reports whether MacWhisper is currently running."""

    def is_macwhisper_running(self) -> bool:  # pragma: no cover - protocol
        raise NotImplementedError


class PgrepProcessChecker:
    """Default `ProcessChecker` backed by `pgrep` (case-insensitive substring).

    A match on any process whose name contains the pattern (default
    ``macwhisper``) is treated as "running". `pgrep` exits 0 when something
    matched, 1 when nothing did; any other failure is treated conservatively as
    "running" so the engine fails closed rather than risking a live write.
    """

    def __init__(
        self,
        pattern: str = DEFAULT_PROCESS_PATTERN,
        runner: Callable[[list[str]], int] | None = None,
    ) -> None:
        self._pattern = pattern
        self._runner = runner or self._default_runner

    @staticmethod
    def _default_runner(argv: list[str]) -> int:
        proc = subprocess.run(argv, capture_output=True, text=True)  # noqa: S603
        return proc.returncode

    def is_macwhisper_running(self) -> bool:
        try:
            code = self._runner(["pgrep", "-i", self._pattern])
        except (OSError, ValueError):
            # Cannot determine -> fail closed (assume running).
            return True
        if code == 0:
            return True
        if code == 1:
            return False
        return True


class Clock:
    """Structural type: supplies the current UTC time."""

    def now(self) -> datetime:  # pragma: no cover - protocol
        raise NotImplementedError


class SystemClock:
    """Default `Clock` returning timezone-aware UTC ``datetime.now``."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------


def _configure(conn: sqlite3.Connection) -> sqlite3.Connection:
    conn.row_factory = sqlite3.Row
    return conn


def open_readonly(path: Path) -> sqlite3.Connection:
    """Open `path` with a read-only SQLite URI (the default-safe mode, §1)."""
    uri = f"file:{Path(path)}?mode=ro"
    return _configure(sqlite3.connect(uri, uri=True))


def open_in_memory() -> sqlite3.Connection:
    """Open a fresh in-memory database (used by tests and dry assembly)."""
    return _configure(sqlite3.connect(":memory:"))


def open_readwrite(
    path: Path,
    *,
    process_checker: ProcessChecker | None = None,
    checkpoint: bool = True,
) -> sqlite3.Connection:
    """Open `path` read-write, enforcing the §1 write preconditions.

    Order of operations:
      1. Refuse if MacWhisper is running (raise `MacWhisperRunningError`).
      2. Connect read-write with foreign-key enforcement on (so the engine's
         parent-before-child insert order is validated, §9).
      3. `PRAGMA wal_checkpoint(TRUNCATE)` so `main.sqlite` is self-contained
         before any backup/write — never touch the `-wal`/`-shm` sidecars by
         hand (§1).

    Args:
        path: Path to `main.sqlite`.
        process_checker: Injected liveness check; defaults to `PgrepProcessChecker`.
        checkpoint: Set False only for tests against an already-quiescent file.

    Raises:
        MacWhisperRunningError: If MacWhisper appears to be running.
    """
    checker = process_checker or PgrepProcessChecker()
    if checker.is_macwhisper_running():
        raise MacWhisperRunningError(
            "MacWhisper appears to be running. Quit it fully (not just the "
            "window) before any read-write database operation."
        )
    conn = _configure(sqlite3.connect(str(Path(path))))
    conn.execute("PRAGMA foreign_keys = ON")
    if checkpoint:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    return conn


# ---------------------------------------------------------------------------
# BLOB-UUID / hex conventions (§3.1)
# ---------------------------------------------------------------------------


def new_uuid_bytes() -> bytes:
    """Return a fresh random 16-byte UUID suitable for a BLOB primary key."""
    return _uuid.uuid4().bytes


def to_hex(value: bytes | str | None) -> str | None:
    """Project a BLOB id to lowercase 32-char hex (§3.1). Pass-through for str."""
    if value is None:
        return None
    if isinstance(value, str):
        return value.lower()
    return value.hex()


def hex_to_bytes(hex_str: str) -> bytes:
    """Convert a 32-char hex id back to the 16-byte BLOB form for `WHERE id = ?`."""
    return bytes.fromhex(hex_str)


def bytes_to_canonical_uuid(value: bytes) -> str:
    """Render a BLOB id as the uppercase 8-4-4-4-12 form used in filenames (§7.1)."""
    return str(_uuid.UUID(bytes=value)).upper()


def hex_to_canonical_uuid(hex_str: str) -> str:
    """Render a 32-char hex id as the uppercase canonical filename prefix (§7.1)."""
    return bytes_to_canonical_uuid(hex_to_bytes(hex_str))


# ---------------------------------------------------------------------------
# Time model (§3.2)
# ---------------------------------------------------------------------------


_DB_DATETIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
)


def parse_db_datetime(value: str | None) -> datetime | None:
    """Parse a MacWhisper wall-clock TEXT timestamp into a UTC `datetime`.

    Accepts both the millisecond and second forms and a stray ``T`` separator
    (§3.2). Returns None when the value is empty or unparseable.
    """
    if not value:
        return None
    text = value.strip().replace("T", " ")
    for fmt in _DB_DATETIME_FORMATS:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def format_db_datetime(dt: datetime) -> str:
    """Format a `datetime` as MacWhisper's UTC ``'YYYY-MM-DD HH:MM:SS.fff'`` (§3.2)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    millis = dt.microsecond // 1000
    return dt.strftime("%Y-%m-%d %H:%M:%S.") + f"{millis:03d}"


def mac_absolute_to_unix(value: float) -> float:
    """Convert a Mac-absolute-time DOUBLE (e.g. `dateDeleted`) to a Unix timestamp."""
    return value + MAC_ABSOLUTE_EPOCH_OFFSET


def unix_to_mac_absolute(value: float) -> float:
    """Convert a Unix timestamp to Mac absolute time (§3.2). Engine never writes this."""
    return value - MAC_ABSOLUTE_EPOCH_OFFSET


# ---------------------------------------------------------------------------
# Schema-drift column resolution (§8)
# ---------------------------------------------------------------------------


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    """Return the live column-name set for `table` via `PRAGMA table_info`.

    `PRAGMA table_info` is authoritative for what columns exist right now;
    `grdb_migrations` is only a secondary signal (§8).
    """
    cur = conn.execute(f"PRAGMA table_info({table})")
    return {row["name"] for row in cur.fetchall()}


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name = ?",
        (table,),
    )
    return cur.fetchone() is not None


def first_present(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    """Return the first candidate column that exists, else None (drift-tolerant)."""
    present = set(columns)
    for name in candidates:
        if name in present:
            return name
    return None


def resolve_model_column(columns: Iterable[str]) -> str | None:
    """Pick the session model-id column, tolerating the `modelIdentifer` typo (§8)."""
    return first_present(columns, ("modelIdentifer", "modelIdentifier"))


def resolve_session_duration_column(columns: Iterable[str]) -> str | None:
    """Pick the session duration column, preferring `playbackDuration` (§8)."""
    return first_present(columns, ("playbackDuration", "duration"))


def insertable_columns(
    conn: sqlite3.Connection,
    table: str,
    values: Mapping[str, object],
) -> dict[str, object]:
    """Filter `values` down to columns that actually exist on `table` (§8).

    This is how the write path degrades gracefully across schema versions: a
    column the current schema lacks is simply omitted from the INSERT rather
    than failing the whole operation.
    """
    present = table_columns(conn, table)
    return {k: v for k, v in values.items() if k in present}


def build_insert(table: str, row: Mapping[str, object]) -> tuple[str, list[object]]:
    """Build a parameterized ``INSERT INTO table (...) VALUES (...)`` statement."""
    cols = list(row.keys())
    if not cols:
        raise ValueError(f"refusing to build an empty INSERT for {table!r}")
    placeholders = ", ".join("?" for _ in cols)
    col_list = ", ".join(cols)
    sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"
    return sql, [row[c] for c in cols]
