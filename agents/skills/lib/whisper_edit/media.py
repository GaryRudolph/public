"""Audio probing, sample-accurate cutting/concat, and filename generation.

The real `ffmpeg`/`ffprobe` work lives behind the `MediaTool` protocol so the
rest of the engine — and its tests — never shell out. `FfmpegMediaTool` is the
production implementation; tests inject a fake.

Two things in this module are deliberately overridable because they encode
**unverified** assumptions from `specs/macwhisper-database.md` §10:

- `HexSuffixStrategy` — the 8-hex filename suffix (§7.1). We only know it is
  *not* `originalFileHash`. Default is a random per-file value; if MacWhisper
  turns out to validate it as a content hash, swap in `ContentHashSuffix` (or a
  faithful re-derivation) without touching the rest of the engine.
- Whether to even produce a `mergedMultitrack` track is decided upstream
  (`TargetBundle.include_merged_multitrack`, §10.2); this module just renders
  whatever tracks it is handed.

`cut`/`concat` re-encode to AAC on purpose: `-c copy` AAC edits drift by up to a
frame, which would desync the transcript (§Risks). Sample-accurate output
trimming keeps the audio aligned with the rebased `transcriptline` timings.
"""

from __future__ import annotations

import secrets
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from . import db
from .model import AudioCut, TargetAudio

DEFAULT_AAC_BITRATE = "256k"


class MediaError(db.WhisperEditError):
    """Raised when an `ffmpeg`/`ffprobe` invocation fails or output is missing."""


# ---------------------------------------------------------------------------
# 8-hex filename suffix strategy (isolated unverified assumption, §10.1)
# ---------------------------------------------------------------------------


class HexSuffixStrategy:
    """Structural type producing the 8-char uppercase hex filename suffix (§7.1)."""

    def derive(self, *, source_path: Path | None, output_path: Path | None) -> str:  # pragma: no cover - protocol
        raise NotImplementedError


class RandomHexSuffix:
    """Default suffix: a random 8-hex value.

    Correct iff the suffix is a per-file disambiguator (the working assumption).
    Uses `secrets` so collisions are vanishingly unlikely without depending on
    any unverified derivation.
    """

    def derive(self, *, source_path: Path | None = None, output_path: Path | None = None) -> str:
        return secrets.token_hex(4).upper()


class ContentHashSuffix:
    """Alternative suffix derived from the output file's bytes.

    A placeholder for the case where backup testing shows MacWhisper validates
    the suffix as a content hash. The exact algorithm is unknown (§10.1); this
    gives a deterministic hook to replace once verified. Not used by default.
    """

    def __init__(self, length: int = 8) -> None:
        self._length = length

    def derive(self, *, source_path: Path | None = None, output_path: Path | None = None) -> str:
        import hashlib

        target = output_path or source_path
        if target is None or not Path(target).exists():
            # Fall back to random rather than emitting a constant suffix.
            return RandomHexSuffix().derive()
        digest = hashlib.sha256(Path(target).read_bytes()).hexdigest()
        return digest[: self._length].upper()


def make_media_filename(
    owner_canonical_uuid: str,
    token: str,
    suffix_8hex: str,
    extension: str = "m4a",
) -> str:
    """Compose ``<UUID>_<token>_<8HEX>.<ext>`` (§7.1).

    `owner_canonical_uuid` must already be the uppercase 8-4-4-4-12 form of the
    owning FK row (see `db.hex_to_canonical_uuid`).
    """
    ext = extension.lstrip(".")
    return f"{owner_canonical_uuid}_{token}_{suffix_8hex}.{ext}"


# ---------------------------------------------------------------------------
# Media tool abstraction
# ---------------------------------------------------------------------------


class MediaTool:
    """Structural type for probing and editing audio (see `FfmpegMediaTool`)."""

    def probe_duration_ms(self, path: Path) -> int:  # pragma: no cover - protocol
        raise NotImplementedError

    def cut(self, src: Path, dst: Path, start_ms: int, end_ms: int | None) -> None:  # pragma: no cover - protocol
        raise NotImplementedError

    def concat(self, srcs: Sequence[Path], dst: Path) -> None:  # pragma: no cover - protocol
        raise NotImplementedError


class FfmpegMediaTool(MediaTool):
    """`MediaTool` backed by `ffmpeg`/`ffprobe` 8.x (re-encoding AAC for alignment)."""

    def __init__(
        self,
        ffmpeg: str = "ffmpeg",
        ffprobe: str = "ffprobe",
        bitrate: str = DEFAULT_AAC_BITRATE,
    ) -> None:
        self._ffmpeg = ffmpeg
        self._ffprobe = ffprobe
        self._bitrate = bitrate

    def _run(self, argv: list[str]) -> subprocess.CompletedProcess:
        try:
            proc = subprocess.run(argv, capture_output=True, text=True)  # noqa: S603
        except OSError as exc:
            raise MediaError(f"failed to launch {argv[0]!r}: {exc}") from exc
        if proc.returncode != 0:
            raise MediaError(
                f"{argv[0]} exited {proc.returncode}: {proc.stderr.strip()[:500]}"
            )
        return proc

    def probe_duration_ms(self, path: Path) -> int:
        proc = self._run(
            [
                self._ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=nokey=1:noprint_wrappers=1",
                str(path),
            ]
        )
        text = proc.stdout.strip()
        try:
            return int(round(float(text) * 1000))
        except ValueError as exc:
            raise MediaError(f"could not parse duration from ffprobe: {text!r}") from exc

    def cut(self, src: Path, dst: Path, start_ms: int, end_ms: int | None) -> None:
        # Output-side -ss/-to (after -i) decodes then trims, which is
        # sample-accurate. Combined with AAC re-encode this keeps the audio
        # aligned with rebased transcript timings (§Risks).
        argv = [self._ffmpeg, "-nostdin", "-y", "-i", str(src), "-vn"]
        argv += ["-ss", _ms_to_ffmpeg_ts(start_ms)]
        if end_ms is not None:
            argv += ["-to", _ms_to_ffmpeg_ts(end_ms)]
        argv += ["-c:a", "aac", "-b:a", self._bitrate, "-movflags", "+faststart", str(dst)]
        self._run(argv)

    def concat(self, srcs: Sequence[Path], dst: Path) -> None:
        if not srcs:
            raise MediaError("concat requires at least one source")
        if len(srcs) == 1:
            self.cut(srcs[0], dst, 0, None)
            return
        argv = [self._ffmpeg, "-nostdin", "-y"]
        for src in srcs:
            argv += ["-i", str(src)]
        inputs = "".join(f"[{i}:a]" for i in range(len(srcs)))
        filtergraph = f"{inputs}concat=n={len(srcs)}:v=0:a=1[out]"
        argv += [
            "-filter_complex",
            filtergraph,
            "-map",
            "[out]",
            "-c:a",
            "aac",
            "-b:a",
            self._bitrate,
            "-movflags",
            "+faststart",
            str(dst),
        ]
        self._run(argv)


def _ms_to_ffmpeg_ts(ms: int) -> str:
    """Render milliseconds as an `ffmpeg` ``S.mmm`` timestamp."""
    return f"{ms / 1000:.3f}"


# ---------------------------------------------------------------------------
# Staging
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StagedAudio:
    """A produced audio track in the temp staging dir, with its probed duration."""

    target: TargetAudio
    path: Path
    duration_ms: int


def stage_target_audio(
    target_audio: TargetAudio,
    *,
    tool: MediaTool,
    work_dir: Path,
    index: int,
) -> StagedAudio:
    """Render one `TargetAudio` into `work_dir` and probe the result.

    A single cut is trimmed directly; multiple cuts are each trimmed to a
    temp part and then concatenated (the `combine` path). This writes only to
    the staging directory — never to `ExternalMedia/` (that move happens in the
    `apply` phase).
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    out_name = f"stage_{index:02d}_{target_audio.track_token}.{target_audio.file_extension}"
    out_path = work_dir / out_name

    if len(target_audio.cuts) == 1:
        cut = target_audio.cuts[0]
        _validate_cut(cut)
        tool.cut(cut.source_path, out_path, cut.start_ms, cut.end_ms)
    else:
        parts: list[Path] = []
        with tempfile.TemporaryDirectory(dir=str(work_dir)) as part_dir:
            for i, cut in enumerate(target_audio.cuts):
                _validate_cut(cut)
                part = Path(part_dir) / f"part_{i:02d}.{target_audio.file_extension}"
                tool.cut(cut.source_path, part, cut.start_ms, cut.end_ms)
                parts.append(part)
            tool.concat(parts, out_path)

    duration_ms = tool.probe_duration_ms(out_path)
    return StagedAudio(target=target_audio, path=out_path, duration_ms=duration_ms)


def _validate_cut(cut: AudioCut) -> None:
    if not Path(cut.source_path).exists():
        raise MediaError(f"source audio not found: {cut.source_path}")
    if cut.start_ms < 0:
        raise MediaError(f"negative start_ms in cut: {cut.start_ms}")
    if cut.end_ms is not None and cut.end_ms <= cut.start_ms:
        raise MediaError(
            f"non-positive cut span: start={cut.start_ms} end={cut.end_ms}"
        )


def move_into_external_media(
    staged_path: Path,
    external_media_dir: Path,
    filename: str,
    *,
    mover=shutil.move,
) -> Path:
    """Move a staged file into `ExternalMedia/` as `filename`, guarding traversal.

    Returns the final path. Raises if the resolved destination escapes
    `external_media_dir` (defence against a crafted token/filename).
    """
    external_media_dir = Path(external_media_dir)
    external_media_dir.mkdir(parents=True, exist_ok=True)
    dest = (external_media_dir / filename).resolve()
    base = external_media_dir.resolve()
    if base not in dest.parents and dest.parent != base:
        raise MediaError(f"refusing to write outside ExternalMedia: {dest}")
    mover(str(staged_path), str(dest))
    return dest
