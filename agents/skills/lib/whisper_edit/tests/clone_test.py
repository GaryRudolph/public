"""Unit tests for clone materialization + verification against an in-memory DB."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import support  # noqa: E402

from whisper_edit import clone, db, media, model, split, verify
from whisper_edit.model import OwnerKind


def _stage(target: model.TargetBundle, tool: media.MediaTool, work_dir: Path):
    return [
        media.stage_target_audio(ta, tool=tool, work_dir=work_dir, index=i)
        for i, ta in enumerate(target.audio)
    ]


class _CloneCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.external = self.tmp / "ExternalMedia"
        self.conn = db.open_in_memory()
        self.conn.execute("PRAGMA foreign_keys = ON")
        support.build_schema(self.conn)
        self.meeting_hex = support.seed_meeting(self.conn, self.external)
        self.memo_hex = support.seed_voice_memo(self.conn, self.external)
        self.tool = support.FakeMediaTool(duration_ms=120000)

    def tearDown(self) -> None:
        self.conn.close()
        self._tmp.cleanup()

    def _meeting(self) -> model.Bundle:
        return model.load_bundle(self.conn, self.meeting_hex, external_media_dir=self.external)

    def _memo(self) -> model.Bundle:
        return model.load_bundle(self.conn, self.memo_hex, external_media_dir=self.external)

    def _plan_first_half(self) -> clone.ClonePlan:
        a, _ = split.split_bundle(self._meeting(), 120000)
        staged = _stage(a, self.tool, self.tmp / "stage")
        return clone.plan_clone(
            a,
            staged_audio=staged,
            uuid_factory=support.sequential_uuid_factory(),
            hex_suffix=support.FixedHexSuffix(),
            clock=support.FixedClock(),
        )


class TestPlanClone(_CloneCase):
    def test_clears_ai_columns_and_suffixes_title(self) -> None:
        """The plan clears aiSummary/aiTitle and applies the Split 1 suffix."""
        plan = self._plan_first_half()
        self.assertIsNone(plan.session_row["aiSummary"])
        self.assertIsNone(plan.session_row["aiTitle"])
        self.assertTrue(plan.final_title.endswith(" - Split 1"))

    def test_recomputes_full_text_and_preview(self) -> None:
        """fullText/textPreview are recomputed from the part's lines (§6)."""
        plan = self._plan_first_half()
        self.assertIn("Morning everyone.", plan.full_text)
        self.assertNotIn("old full text", plan.full_text)
        self.assertTrue(plan.text_preview)

    def test_carries_model_fields_but_not_blobs(self) -> None:
        """Non-AI scalar columns carry forward; BLOB columns never do."""
        plan = self._plan_first_half()
        self.assertEqual(plan.session_row["modelEngine"], "parakeetKitPro")
        self.assertEqual(plan.session_row["modelIdentifer"], "nvidia_parakeet-v3")
        # The carried source id must not leak; identity is freshly assigned.
        self.assertNotEqual(plan.session_row["id"], self.meeting_hex)

    def test_filenames_use_new_uuid_prefixes(self) -> None:
        """Session-owned tracks use the new session UUID as the filename prefix (§7.1)."""
        plan = self._plan_first_half()
        session_canonical = db.hex_to_canonical_uuid(plan.new_session_id_hex)
        session_tracks = [m for m in plan.media if m.owner_column == "sessionID"]
        self.assertTrue(session_tracks)
        for m in session_tracks:
            self.assertTrue(m.filename.startswith(session_canonical))

    def test_round_trips_through_json(self) -> None:
        """A ClonePlan survives to_dict/from_dict for the plan->apply hand-off."""
        plan = self._plan_first_half()
        restored = clone.ClonePlan.from_dict(plan.to_dict())
        self.assertEqual(restored.new_session_id_hex, plan.new_session_id_hex)
        self.assertEqual(len(restored.lines), len(plan.lines))
        self.assertEqual(len(restored.media), len(plan.media))


class TestApplyClone(_CloneCase):
    def test_inserts_meeting_session_and_verifies(self) -> None:
        """Applying a split half inserts all rows and passes verification."""
        plan = self._plan_first_half()
        result = clone.apply_clone(self.conn, plan, external_media_dir=self.external)
        self.assertEqual(result.inserted_lines, 3)
        self.assertEqual(result.inserted_media, 5)
        self.assertEqual(result.inserted_speaker_links, 1)  # only Gary speaks in part 1

        # Part 1 spans 0..60000ms; point the duration probe at a matching value
        # (the fake tool can't model per-track durations).
        aligned_tool = support.FakeMediaTool(duration_ms=60000)
        report = verify.verify_clone(
            self.conn, plan, external_media_dir=self.external, tool=aligned_tool
        )
        self.assertTrue(report.ok, msg=str(report.failures()))

    def test_source_session_retained(self) -> None:
        """The source session and its media are untouched after apply (§1)."""
        plan = self._plan_first_half()
        clone.apply_clone(self.conn, plan, external_media_dir=self.external)
        cur = self.conn.execute(
            "SELECT COUNT(*) FROM session WHERE id = ?", (db.hex_to_bytes(self.meeting_hex),)
        )
        self.assertEqual(cur.fetchone()[0], 1)
        cur = self.conn.execute(
            "SELECT COUNT(*) FROM mediafile WHERE sessionID = ?",
            (db.hex_to_bytes(self.meeting_hex),),
        )
        self.assertEqual(cur.fetchone()[0], 3)  # source session tracks still present

    def test_foreign_keys_intact_after_apply(self) -> None:
        """No FK violations remain (insert order respected, §9)."""
        plan = self._plan_first_half()
        clone.apply_clone(self.conn, plan, external_media_dir=self.external)
        self.assertEqual(self.conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_voice_memo_media_link_wired(self) -> None:
        """The circular voicememos.mediaFileID back-link is set after apply."""
        b = self._memo()
        a2, _ = split.split_bundle(b, 20000)
        staged = _stage(a2, self.tool, self.tmp / "stage_memo")
        plan = clone.plan_clone(
            a2, staged_audio=staged,
            uuid_factory=support.sequential_uuid_factory(100),
            hex_suffix=support.FixedHexSuffix(100), clock=support.FixedClock(),
        )
        clone.apply_clone(self.conn, plan, external_media_dir=self.external)
        cur = self.conn.execute(
            "SELECT mediaFileID FROM voicememos WHERE id = ?",
            (db.hex_to_bytes(plan.parent_id_hex),),
        )
        self.assertIsNotNone(cur.fetchone()[0])

    @unittest.skipUnless(support.has_fts5(), "sqlite build lacks FTS5")
    def test_new_session_is_fts_searchable(self) -> None:
        """A plain INSERT makes the session searchable via sessionFTS (§6, §10.6)."""
        plan = self._plan_first_half()
        clone.apply_clone(self.conn, plan, external_media_dir=self.external)
        cur = self.conn.execute("SELECT COUNT(*) FROM sessionFTS WHERE sessionFTS MATCH 'release'")
        self.assertGreaterEqual(cur.fetchone()[0], 1)


class TestVerificationFailures(_CloneCase):
    def test_missing_media_file_fails_verification(self) -> None:
        """A missing ExternalMedia file is reported as a failure."""
        plan = self._plan_first_half()
        clone.apply_clone(self.conn, plan, external_media_dir=self.external)
        # Delete one written file to simulate corruption.
        (self.external / plan.media[0].filename).unlink()
        report = verify.verify_clone(self.conn, plan, external_media_dir=self.external)
        self.assertFalse(report.ok)

    def test_duration_drift_flagged(self) -> None:
        """A probed duration far from the last line end fails alignment."""
        plan = self._plan_first_half()
        clone.apply_clone(self.conn, plan, external_media_dir=self.external)
        bad_tool = support.FakeMediaTool(duration_ms=999999)  # wildly off
        report = verify.verify_clone(
            self.conn, plan, external_media_dir=self.external, tool=bad_tool
        )
        align = [c for c in report.checks if c.name == "duration_alignment"][0]
        self.assertFalse(align.ok)


if __name__ == "__main__":
    unittest.main()
