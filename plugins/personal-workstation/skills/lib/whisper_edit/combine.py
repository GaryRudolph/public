"""Combine two `Bundle`s into one `TargetBundle` (A then B).

The transform is the inverse of `split`: A's lines keep their time base, B's
lines are offset by A's duration (with `wordsJson` timings shifted to match,
§5.2), and the speaker sets are unioned. Each audio track is the concat of A's
track then B's track of the same role, so the merged session reproduces the
full §7.3 track set.

The two bundles must be the same kind and expose the same set of audio roles
(`(media_type, token)`); otherwise there is no faithful way to concat tracks
and we raise rather than silently dropping audio.
"""

from __future__ import annotations

from typing import Mapping

from . import db
from .model import (
    AudioCut,
    Bundle,
    MediaType,
    SessionKind,
    TargetAudio,
    TargetBundle,
    TargetLine,
    shift_words_json,
)


def combine_bundles(
    bundle_a: Bundle,
    bundle_b: Bundle,
    *,
    title_suffix: str = " - Combined",
    include_merged_multitrack: bool = True,
) -> TargetBundle:
    """Combine `bundle_a` then `bundle_b` into a single `TargetBundle`.

    Args:
        bundle_a: First session (keeps its time base, plays first).
        bundle_b: Second session (offset after A).
        title_suffix: Suffix applied by clone to A's title.
        include_merged_multitrack: Reconstruct `mergedMultitrack` (§10.2).

    Raises:
        ValueError: If the kinds differ, a duration is unknown, or the audio
            roles do not line up between A and B.
    """
    if bundle_a.kind != bundle_b.kind:
        raise ValueError(
            f"cannot combine different kinds: {bundle_a.kind.value} + {bundle_b.kind.value}"
        )
    offset_ms = bundle_a.duration_ms()
    if offset_ms is None:
        raise ValueError("bundle A has no determinable duration; cannot offset B")

    lines_a = [_to_target_line(l, 0) for l in bundle_a.transcript_lines]
    lines_b = [_to_target_line(l, -offset_ms) for l in bundle_b.transcript_lines]
    lines = tuple(lines_a + lines_b)

    speaker_ids = tuple(
        sorted(
            {s.id_hex for s in bundle_a.speakers} | {s.id_hex for s in bundle_b.speakers}
        )
    )

    dur_b = bundle_b.duration_ms()
    total_duration = offset_ms + dur_b if dur_b is not None else None

    audio = _concat_audio(bundle_a, bundle_b, include_merged_multitrack)

    parent_raw: Mapping[str, object] = {}
    if bundle_a.recorded_meeting is not None:
        parent_raw = dict(bundle_a.recorded_meeting.raw)
    elif bundle_a.voice_memo is not None:
        parent_raw = dict(bundle_a.voice_memo.raw)

    return TargetBundle(
        kind=bundle_a.kind,
        title=bundle_a.title,
        title_suffix=title_suffix,
        date_created=bundle_a.session.date_created or "",
        duration_ms=total_duration,
        lines=lines,
        speaker_ids=speaker_ids,
        audio=audio,
        is_merged_from_multiple_tracks=(bundle_a.kind == SessionKind.MEETING),
        source_session_id_hex=bundle_a.session.id_hex,
        carried_session_fields=dict(bundle_a.session.raw),
        carried_parent_fields=parent_raw,
        include_merged_multitrack=include_merged_multitrack,
    )


def _to_target_line(line, offset_ms: int) -> TargetLine:
    # offset_ms is subtracted, mirroring split: pass a negative value to shift later.
    return TargetLine(
        start_ms=line.start_ms - offset_ms,
        end_ms=line.end_ms - offset_ms,
        text=line.text,
        speaker_id_hex=line.speaker_id_hex,
        words_json=shift_words_json(line.words_json, -offset_ms),
        is_favorite=line.is_favorite,
    )


def _concat_audio(
    bundle_a: Bundle, bundle_b: Bundle, include_merged_multitrack: bool
) -> tuple[TargetAudio, ...]:
    a_by_role = _audio_by_role(bundle_a, include_merged_multitrack)
    b_by_role = _audio_by_role(bundle_b, include_merged_multitrack)
    if set(a_by_role) != set(b_by_role):
        raise ValueError(
            "audio roles do not match between bundles: "
            f"{sorted(a_by_role)} vs {sorted(b_by_role)}"
        )
    out: list[TargetAudio] = []
    for role in sorted(a_by_role):
        mf_a = a_by_role[role]
        mf_b = b_by_role[role]
        out.append(
            TargetAudio(
                media_type=mf_a.type,
                track_token=mf_a.token,
                owner=mf_a.owner_kind,
                cuts=(
                    AudioCut(source_path=mf_a.path, start_ms=0, end_ms=None),
                    AudioCut(source_path=mf_b.path, start_ms=0, end_ms=None),
                ),
                playback_type=mf_a.playback_type,
                file_extension=(mf_a.file_extension or "m4a"),
            )
        )
    return tuple(out)


def _audio_by_role(bundle: Bundle, include_merged_multitrack: bool) -> dict[tuple[str, str], object]:
    out: dict[tuple[str, str], object] = {}
    for mf in bundle.media_files:
        if not include_merged_multitrack and mf.type == MediaType.MERGED_MULTITRACK.value:
            continue
        key = (mf.type, mf.token)
        if key in out:
            raise db.WhisperEditError(f"duplicate audio role {key} in bundle {bundle.session.id_hex}")
        out[key] = mf
    return out
