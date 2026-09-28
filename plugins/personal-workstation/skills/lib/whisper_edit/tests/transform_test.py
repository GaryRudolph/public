"""Unit tests for the pure transforms: model loading, split, combine."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import support  # noqa: E402

from whisper_edit import combine, db, model, split
from whisper_edit.model import OwnerKind, SessionKind


class _SeededCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.external = self.tmp / "ExternalMedia"
        self.conn = db.open_in_memory()
        support.build_schema(self.conn, with_fts=False)
        self.meeting_hex = support.seed_meeting(self.conn, self.external)
        self.memo_hex = support.seed_voice_memo(self.conn, self.external)

    def tearDown(self) -> None:
        self.conn.close()
        self._tmp.cleanup()

    def meeting(self) -> model.Bundle:
        return model.load_bundle(self.conn, self.meeting_hex, external_media_dir=self.external)

    def memo(self) -> model.Bundle:
        return model.load_bundle(self.conn, self.memo_hex, external_media_dir=self.external)


class TestBundleLoader(_SeededCase):
    def test_loads_meeting_with_five_media(self) -> None:
        """A meeting loads 5 media files across two parent rows (§7.3)."""
        b = self.meeting()
        self.assertEqual(b.kind, SessionKind.MEETING)
        self.assertEqual(len(b.media_files), 5)
        self.assertEqual(len(b.session_audio()), 3)
        self.assertEqual(len(b.parent_audio()), 2)
        self.assertEqual(len(b.transcript_lines), 6)
        self.assertIsNotNone(b.recorded_meeting)

    def test_media_tokens_parsed(self) -> None:
        """track-0 / track-1 tokens are recovered from filenames (§7.1)."""
        tokens = sorted(m.token for m in self.meeting().media_files)
        self.assertEqual(
            tokens, ["app-audio", "merged-audio", "mic-audio", "track-0", "track-1"]
        )

    def test_loads_voice_memo(self) -> None:
        """A voice memo loads as a single-track VOICE_MEMO bundle."""
        b = self.memo()
        self.assertEqual(b.kind, SessionKind.VOICE_MEMO)
        self.assertEqual(len(b.media_files), 1)
        self.assertEqual(b.media_files[0].owner_kind, OwnerKind.PARENT)


class TestSplitTransform(_SeededCase):
    def test_partitions_lines_and_rebases(self) -> None:
        """Lines split at the gap; part 2 is rebased to start near zero."""
        a, b = split.split_bundle(self.meeting(), 120000)
        self.assertEqual(len(a.lines), 3)
        self.assertEqual(len(b.lines), 3)
        self.assertEqual(a.lines[0].start_ms, 0)
        self.assertEqual(b.lines[0].start_ms, 0)  # 120000 - 120000
        self.assertEqual(b.lines[-1].end_ms, 178000 - 120000)

    def test_each_half_cuts_all_tracks(self) -> None:
        """Both halves reproduce all 5 tracks with correct cut spans."""
        a, b = split.split_bundle(self.meeting(), 120000)
        self.assertEqual(len(a.audio), 5)
        self.assertEqual(len(b.audio), 5)
        for ta in a.audio:
            self.assertEqual(ta.cuts[0].start_ms, 0)
            self.assertEqual(ta.cuts[0].end_ms, 120000)
        for tb in b.audio:
            self.assertEqual(tb.cuts[0].start_ms, 120000)
            self.assertIsNone(tb.cuts[0].end_ms)

    def test_title_suffixes_distinct(self) -> None:
        """The two halves carry the Split 1 / Split 2 suffixes."""
        a, b = split.split_bundle(self.meeting(), 120000)
        self.assertEqual(a.title_suffix, " - Split 1")
        self.assertEqual(b.title_suffix, " - Split 2")

    def test_can_omit_merged_multitrack(self) -> None:
        """The mergedMultitrack track can be dropped (unverified assumption §10.2)."""
        a, _ = split.split_bundle(self.meeting(), 120000, include_merged_multitrack=False)
        types = {ta.media_type for ta in a.audio}
        self.assertNotIn(model.MediaType.MERGED_MULTITRACK.value, types)
        self.assertEqual(len(a.audio), 4)

    def test_rejects_out_of_range_split(self) -> None:
        """A split at/after the duration is rejected."""
        with self.assertRaises(ValueError):
            split.split_bundle(self.meeting(), 999999)
        with self.assertRaises(ValueError):
            split.split_bundle(self.meeting(), 0)

    def test_words_json_rebased_in_part_one(self) -> None:
        """Part 1 keeps its time base; the first line's words are unshifted."""
        a, _ = split.split_bundle(self.meeting(), 120000)
        self.assertIn('"startTime":0', a.lines[0].words_json)


class TestSplitDetection(_SeededCase):
    def test_detects_silence_gap(self) -> None:
        """The 60s gap surfaces as a high-scored silence candidate at 120000ms."""
        candidates = split.detect_split_candidates(self.meeting())
        self.assertTrue(candidates)
        top = candidates[0]
        self.assertEqual(top.split_ms, 120000)
        self.assertIn("silence", top.reason)

    def test_speaker_onset_detected(self) -> None:
        """A new persistent speaker joining is offered as a candidate."""
        reasons = {c.reason for c in split.detect_split_candidates(self.meeting())}
        self.assertTrue(any("speaker" in r for r in reasons))

    def test_context_attached(self) -> None:
        """Candidates carry surrounding transcript context."""
        top = split.detect_split_candidates(self.meeting())[0]
        self.assertTrue(top.before_context)
        self.assertTrue(top.after_context)


class TestCombineTransform(_SeededCase):
    def test_offsets_second_bundle(self) -> None:
        """Combining two memos offsets B's lines by A's duration."""
        a = self.memo()
        b = self.memo()
        combined = combine.combine_bundles(a, b)
        offset = a.duration_ms()
        self.assertEqual(len(combined.lines), 6)
        self.assertEqual(combined.lines[3].start_ms, offset)  # first B line

    def test_audio_concat_per_role(self) -> None:
        """Each role becomes a two-cut concat (A then B)."""
        combined = combine.combine_bundles(self.memo(), self.memo())
        self.assertEqual(len(combined.audio), 1)
        self.assertEqual(len(combined.audio[0].cuts), 2)

    def test_speaker_union(self) -> None:
        """Speakers from both bundles are unioned."""
        combined = combine.combine_bundles(self.meeting(), self.meeting())
        self.assertEqual(len(combined.speaker_ids), 2)

    def test_rejects_mismatched_kinds(self) -> None:
        """Combining a meeting with a memo is rejected."""
        with self.assertRaises(ValueError):
            combine.combine_bundles(self.meeting(), self.memo())


if __name__ == "__main__":
    unittest.main()
