"""Shared engine for the MacWhisper split/combine skills.

This package is the one tested code path for *writing* to MacWhisper's
`main.sqlite` + `ExternalMedia/`. The three planned skills
(`personal-whisper-split-db`, `-combine-db`, `-split-combine-db`) are thin
entry points that call these library functions in-process; the orchestrator
skill composes split + combine here rather than re-invoking the other skills.

Read `specs/macwhisper-database.md` for the schema, time model, soft-delete,
FTS triggers, the §1 safety contract, and the §10 unverified assumptions this
engine is built to validate against a backup before any real run.

Module map:

- `db`        — guarded read-write open (refuses while MacWhisper runs;
                checkpoints the WAL), hex/UUID/datetime conventions, schema-drift
                column resolution.
- `backup`    — timestamped DB + referenced-media backup with a rollback manifest.
- `model`     — immutable source types + the read-only `Bundle` loader, plus the
                UUID-free target types (`TargetBundle`) used by split/combine/clone.
- `media`     — `ffmpeg`/`ffprobe` behind a protocol, sample-accurate cut/concat,
                filename generation, and the overridable 8-hex suffix strategy.
- `selection` — rank session candidates from fuzzy title/date/time hints.
- `split`     — `split_bundle` + silence/speaker-onset split-point detection.
- `combine`   — `combine_bundles` (offset, speaker union, audio concat).
- `clone`     — pure `plan_clone` + transactional `apply_clone` materialization.
- `verify`    — post-write integrity/alignment/FTS checks.
- `report`    — human summaries (never deletes; never claims to).
- `engine`    — the `identify -> plan -> apply` flow the skills call.

Stdlib-only and runnable on macOS system Python 3.9, matching `lib/whisper/`.
"""

from __future__ import annotations

from . import (
    backup,
    clone,
    combine,
    db,
    media,
    model,
    report,
    selection,
    split,
    verify,
)
from .db import (
    MacWhisperRunningError,
    SchemaError,
    WhisperEditError,
)
from .engine import (
    ApplyResult,
    OperationPlan,
    apply,
    identify,
    load_bundle,
    plan_combine,
    plan_split,
)
from .model import Bundle, SessionKind, TargetBundle

__all__ = [
    # submodules
    "db",
    "backup",
    "model",
    "media",
    "selection",
    "split",
    "combine",
    "clone",
    "verify",
    "report",
    # three-phase flow
    "identify",
    "load_bundle",
    "plan_split",
    "plan_combine",
    "apply",
    "OperationPlan",
    "ApplyResult",
    # common types
    "Bundle",
    "TargetBundle",
    "SessionKind",
    # errors
    "WhisperEditError",
    "MacWhisperRunningError",
    "SchemaError",
]
