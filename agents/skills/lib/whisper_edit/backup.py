"""Timestamped backup of `main.sqlite` (+ sidecars) and referenced media.

A backup is a hard precondition for any write (`specs/macwhisper-database.md`
§1/§9): before the engine mutates `main.sqlite` or `ExternalMedia/`, it copies
the (already WAL-checkpointed) database and every audio file the plan touches
into a timestamped directory, and records a `manifest.json` mapping each
original to its backup copy so a botched run can be rolled back.

The clock and the copy primitive are injected so the manifest is deterministic
under test and so callers can substitute a hardlink/reflink copier if desired.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

from . import db

Copier = Callable[[str, str], object]

MANIFEST_NAME = "manifest.json"
DEFAULT_BACKUP_ROOT = (
    Path.home() / "Library/Application Support/MacWhisper/Backups-whisper-edit"
)


class BackupError(db.WhisperEditError):
    """Raised when a backup cannot be created (missing DB, copy failure)."""


@dataclass(frozen=True)
class BackupManifest:
    """An immutable record of one backup, sufficient to roll a write back."""

    backup_dir: Path
    created_at: str
    db_backups: Mapping[str, str]  # original abs path -> backup abs path
    media_backups: Mapping[str, str]  # original abs path -> backup abs path

    def to_dict(self) -> dict:
        return {
            "backup_dir": str(self.backup_dir),
            "created_at": self.created_at,
            "db_backups": dict(self.db_backups),
            "media_backups": dict(self.media_backups),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "BackupManifest":
        return cls(
            backup_dir=Path(str(data["backup_dir"])),
            created_at=str(data["created_at"]),
            db_backups=dict(data.get("db_backups") or {}),  # type: ignore[arg-type]
            media_backups=dict(data.get("media_backups") or {}),  # type: ignore[arg-type]
        )


def _timestamp(clock: db.Clock) -> str:
    return clock.now().strftime("%Y%m%d-%H%M%S")


def create_backup(
    db_path: Path,
    media_paths: Sequence[Path],
    *,
    backup_root: Path = DEFAULT_BACKUP_ROOT,
    clock: db.Clock | None = None,
    copier: Copier = shutil.copy2,
) -> BackupManifest:
    """Copy the DB (+ `-wal`/`-shm`) and `media_paths` into a timestamped dir.

    The database is expected to have already been WAL-checkpointed by
    `db.open_readwrite`, so the `-wal`/`-shm` sidecars are usually absent; we
    copy them when present for completeness without ever editing them.

    Args:
        db_path: Path to `main.sqlite`.
        media_paths: Every `ExternalMedia/` file the plan references.
        backup_root: Parent directory for the timestamped backup folder.
        clock: Injected clock (defaults to `SystemClock`).
        copier: Injected copy primitive (defaults to `shutil.copy2`).

    Raises:
        BackupError: If the database is missing or a copy fails.
    """
    clock = clock or db.SystemClock()
    db_path = Path(db_path)
    if not db_path.exists():
        raise BackupError(f"database not found, cannot back up: {db_path}")

    backup_dir = Path(backup_root) / f"backup-{_timestamp(clock)}"
    db_dir = backup_dir / "Database"
    media_dir = backup_dir / db.EXTERNAL_MEDIA_DIRNAME
    db_dir.mkdir(parents=True, exist_ok=True)
    media_dir.mkdir(parents=True, exist_ok=True)

    db_backups: dict[str, str] = {}
    try:
        for suffix in ("", "-wal", "-shm"):
            src = Path(str(db_path) + suffix)
            if src.exists():
                dst = db_dir / src.name
                copier(str(src), str(dst))
                db_backups[str(src)] = str(dst)

        media_backups: dict[str, str] = {}
        # De-duplicate while preserving order; a file referenced twice is copied once.
        for src in _unique_paths(media_paths):
            if not src.exists():
                # A referenced-but-missing source is itself a problem the caller
                # should see; record nothing and let verify/plan surface it.
                continue
            dst = media_dir / src.name
            copier(str(src), str(dst))
            media_backups[str(src)] = str(dst)
    except OSError as exc:
        raise BackupError(f"backup copy failed: {exc}") from exc

    manifest = BackupManifest(
        backup_dir=backup_dir,
        created_at=db.format_db_datetime(clock.now()),
        db_backups=db_backups,
        media_backups=media_backups,
    )
    (backup_dir / MANIFEST_NAME).write_text(
        json.dumps(manifest.to_dict(), indent=2), encoding="utf-8"
    )
    return manifest


def restore_backup(manifest: BackupManifest, *, copier: Copier = shutil.copy2) -> None:
    """Copy every backed-up file back over its original (manual rollback).

    Restores the database and the referenced media. Intended for an explicit,
    human-confirmed rollback — the engine never calls this automatically.
    """
    for original, backup in {**manifest.db_backups, **manifest.media_backups}.items():
        if Path(backup).exists():
            Path(original).parent.mkdir(parents=True, exist_ok=True)
            copier(backup, original)


def _unique_paths(paths: Sequence[Path]) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for p in paths:
        key = str(Path(p))
        if key not in seen:
            seen.add(key)
            out.append(Path(p))
    return out
