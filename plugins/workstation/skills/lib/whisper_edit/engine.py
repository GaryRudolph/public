"""Three-phase orchestration: identify -> plan -> apply.

The split/combine skills are thin: they call these functions in-process and
handle interactive disambiguation/approval. Each operation runs the same flow
(`specs/macwhisper-database.md` §9):

1. **identify** — resolve the user's hints to ranked session candidates
   (read-only), then `load_bundle` the chosen one(s).
2. **plan** — build the target session(s) (`split`/`combine`), stage the audio
   cuts into a temp dir, and resolve write-ready `ClonePlan`s. Emits
   `plan.json` + a human summary. **No live writes.**
3. **apply** — open the DB read-write (refusing if MacWhisper is running and
   force-checkpointing the WAL), take a **mandatory** timestamped backup, then
   insert rows + move staged audio + verify. Never deletes the source.

The dangerous boundaries (process check, clock, media tool, file mover, UUID
source, hex-suffix strategy) are all injectable so the whole flow is testable
against an in-memory database with fakes.
"""

from __future__ import annotations

import json
import secrets
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from . import backup, clone, combine, db, media, model, report, selection, split, verify

DEFAULT_PLAN_ROOT = Path("/tmp/whisper_edit")
PLAN_FILENAME = "plan.json"


# ---------------------------------------------------------------------------
# Operation plan (the serializable hand-off between plan and apply)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OperationPlan:
    """A complete, write-ready dry-run plan for one split/combine operation."""

    op: str
    db_path: str
    external_media_dir: str
    source_session_ids: tuple[str, ...]
    clone_plans: tuple[clone.ClonePlan, ...]
    backup_media_paths: tuple[str, ...]
    staging_dir: str

    def to_dict(self) -> dict:
        return {
            "op": self.op,
            "db_path": self.db_path,
            "external_media_dir": self.external_media_dir,
            "source_session_ids": list(self.source_session_ids),
            "clone_plans": [cp.to_dict() for cp in self.clone_plans],
            "backup_media_paths": list(self.backup_media_paths),
            "staging_dir": self.staging_dir,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OperationPlan":
        return cls(
            op=data["op"],
            db_path=data["db_path"],
            external_media_dir=data["external_media_dir"],
            source_session_ids=tuple(data["source_session_ids"]),
            clone_plans=tuple(clone.ClonePlan.from_dict(cp) for cp in data["clone_plans"]),
            backup_media_paths=tuple(data["backup_media_paths"]),
            staging_dir=data["staging_dir"],
        )

    def write(self, path: Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def read(cls, path: Path) -> "OperationPlan":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def summary(self) -> str:
        return report.render_plan_summary(
            self.op,
            self.source_session_ids,
            self.clone_plans,
            staging_dir=self.staging_dir,
            backup_media_count=len(self.backup_media_paths),
        )


@dataclass(frozen=True)
class ApplyResult:
    """Outcome of `apply` for one operation, with verification + backup info."""

    op: str
    source_session_ids: tuple[str, ...]
    results: tuple[clone.CloneResult, ...]
    verifications: tuple[verify.VerificationReport, ...]
    manifest: backup.BackupManifest
    staging_dir: str

    @property
    def ok(self) -> bool:
        return all(v.ok for v in self.verifications)

    def summary(self) -> str:
        return report.render_apply_summary(
            self.op,
            self.source_session_ids,
            self.results,
            self.verifications,
            manifest=self.manifest,
            staging_dir=self.staging_dir,
        )


# ---------------------------------------------------------------------------
# Phase 1: identify
# ---------------------------------------------------------------------------


def external_media_dir_for(db_path: Path) -> Path:
    """`ExternalMedia/` sits beside `main.sqlite` (§2)."""
    return Path(db_path).parent / db.EXTERNAL_MEDIA_DIRNAME


def identify(
    db_path: Path,
    *,
    title: str | None = None,
    date: str | None = None,
    time: str | None = None,
    limit: int = 10,
) -> list[selection.SessionCandidate]:
    """Return ranked session candidates for the user's hints (read-only)."""
    conn = db.open_readonly(db_path)
    try:
        records = selection.load_session_index(conn)
    finally:
        conn.close()
    return selection.rank_candidates(records, title=title, date=date, time=time, limit=limit)


def load_bundle(db_path: Path, session_id_hex: str) -> model.Bundle:
    """Load a full `Bundle` for `session_id_hex` (read-only)."""
    conn = db.open_readonly(db_path)
    try:
        return model.load_bundle(
            conn, session_id_hex, external_media_dir=external_media_dir_for(db_path)
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Phase 2: plan (no live writes)
# ---------------------------------------------------------------------------


def plan_split(
    bundle: model.Bundle,
    *,
    db_path: Path,
    split_ms: int | None = None,
    candidate_index: int = 0,
    include_merged_multitrack: bool = True,
    tool: media.MediaTool | None = None,
    uuid_factory: clone.UuidFactory = db.new_uuid_bytes,
    hex_suffix: media.HexSuffixStrategy | None = None,
    clock: db.Clock | None = None,
    plan_root: Path = DEFAULT_PLAN_ROOT,
) -> OperationPlan:
    """Plan a split. If `split_ms` is None, auto-detect and use `candidate_index`.

    Raises:
        ValueError: If auto-detection finds no candidates or the index is bad.
    """
    if split_ms is None:
        candidates = split.detect_split_candidates(bundle)
        if not candidates:
            raise ValueError(
                "no split point detected; pass split_ms explicitly after reviewing the transcript"
            )
        if candidate_index < 0 or candidate_index >= len(candidates):
            raise ValueError(f"candidate_index {candidate_index} out of range (0..{len(candidates)-1})")
        split_ms = candidates[candidate_index].split_ms

    targets = split.split_bundle(
        bundle, split_ms, include_merged_multitrack=include_merged_multitrack
    )
    return _assemble_plan(
        "split", db_path, [bundle], list(targets),
        tool=tool, uuid_factory=uuid_factory, hex_suffix=hex_suffix,
        clock=clock, plan_root=plan_root,
    )


def plan_combine(
    bundle_a: model.Bundle,
    bundle_b: model.Bundle,
    *,
    db_path: Path,
    include_merged_multitrack: bool = True,
    tool: media.MediaTool | None = None,
    uuid_factory: clone.UuidFactory = db.new_uuid_bytes,
    hex_suffix: media.HexSuffixStrategy | None = None,
    clock: db.Clock | None = None,
    plan_root: Path = DEFAULT_PLAN_ROOT,
) -> OperationPlan:
    """Plan a combine (A then B). No live writes."""
    target = combine.combine_bundles(
        bundle_a, bundle_b, include_merged_multitrack=include_merged_multitrack
    )
    return _assemble_plan(
        "combine", db_path, [bundle_a, bundle_b], [target],
        tool=tool, uuid_factory=uuid_factory, hex_suffix=hex_suffix,
        clock=clock, plan_root=plan_root,
    )


def _assemble_plan(
    op: str,
    db_path: Path,
    source_bundles: Sequence[model.Bundle],
    targets: Sequence[model.TargetBundle],
    *,
    tool: media.MediaTool | None,
    uuid_factory: clone.UuidFactory,
    hex_suffix: media.HexSuffixStrategy | None,
    clock: db.Clock | None,
    plan_root: Path,
) -> OperationPlan:
    clock = clock or db.SystemClock()
    tool = tool or media.FfmpegMediaTool()
    op_id = clock.now().strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3)
    op_dir = Path(plan_root) / op_id
    staging_root = op_dir / "staging"

    clone_plans: list[clone.ClonePlan] = []
    for k, target in enumerate(targets):
        work_dir = staging_root / f"target_{k}"
        staged = [
            media.stage_target_audio(ta, tool=tool, work_dir=work_dir, index=i)
            for i, ta in enumerate(target.audio)
        ]
        clone_plans.append(
            clone.plan_clone(
                target,
                staged_audio=staged,
                uuid_factory=uuid_factory,
                hex_suffix=hex_suffix,
                clock=clock,
            )
        )

    backup_media_paths = tuple(
        sorted({str(m.path) for b in source_bundles for m in b.media_files})
    )
    external_media_dir = str(source_bundles[0].external_media_dir)

    op_plan = OperationPlan(
        op=op,
        db_path=str(Path(db_path)),
        external_media_dir=external_media_dir,
        source_session_ids=tuple(b.session.id_hex for b in source_bundles),
        clone_plans=tuple(clone_plans),
        backup_media_paths=backup_media_paths,
        staging_dir=str(staging_root),
    )
    op_plan.write(op_dir / PLAN_FILENAME)
    op_plan.write(Path(plan_root) / PLAN_FILENAME)  # stable "latest plan" location
    return op_plan


# ---------------------------------------------------------------------------
# Phase 3: apply (guard + backup + write + verify)
# ---------------------------------------------------------------------------


def apply(
    op_plan: OperationPlan,
    *,
    process_checker: db.ProcessChecker | None = None,
    clock: db.Clock | None = None,
    tool: media.MediaTool | None = None,
    mover: Callable[[str, str], Any] = shutil.move,
    backup_root: Path = backup.DEFAULT_BACKUP_ROOT,
) -> ApplyResult:
    """Execute a planned operation: guard, backup, write, verify.

    The order is load-bearing (§9): the read-write open refuses while MacWhisper
    is running and force-checkpoints the WAL; a timestamped backup is then taken
    **before** any write (if the backup fails, nothing is written); only then are
    rows inserted and staged audio moved, followed by verification. The source
    session is never modified or deleted.

    Raises:
        MacWhisperRunningError: If MacWhisper is running.
        BackupError: If the mandatory backup cannot be taken (no writes occur).
    """
    db_path = Path(op_plan.db_path)
    external_media_dir = Path(op_plan.external_media_dir)

    conn = db.open_readwrite(db_path, process_checker=process_checker)
    try:
        # Mandatory backup BEFORE any mutation (acceptance: apply requires a backup).
        manifest = backup.create_backup(
            db_path, [Path(p) for p in op_plan.backup_media_paths],
            backup_root=backup_root, clock=clock,
        )

        results: list[clone.CloneResult] = []
        verifications: list[verify.VerificationReport] = []
        for cp in op_plan.clone_plans:
            results.append(
                clone.apply_clone(conn, cp, external_media_dir=external_media_dir, mover=mover)
            )
            verifications.append(
                verify.verify_clone(conn, cp, external_media_dir=external_media_dir, tool=tool)
            )
    finally:
        conn.close()

    return ApplyResult(
        op=op_plan.op,
        source_session_ids=op_plan.source_session_ids,
        results=tuple(results),
        verifications=tuple(verifications),
        manifest=manifest,
        staging_dir=op_plan.staging_dir,
    )
