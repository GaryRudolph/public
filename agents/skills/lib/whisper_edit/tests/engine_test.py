"""End-to-end tests for the identify -> plan -> apply flow (with fakes)."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

import support  # noqa: E402

from whisper_edit import backup, db, engine


class _EngineCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.db_path = self.tmp / "Database" / "main.sqlite"
        self.external = self.tmp / "Database" / "ExternalMedia"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Seed via a direct connection, then close so the engine can reopen RW.
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA foreign_keys = ON")
        support.build_schema(conn)
        self.meeting_hex = support.seed_meeting(conn, self.external)
        support.seed_voice_memo(conn, self.external)
        conn.close()

        self.tool = support.FakeMediaTool(duration_ms=120000)
        self.plan_root = self.tmp / "plan"
        self.backup_root = self.tmp / "backups"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _session_count(self) -> int:
        conn = db.open_readonly(self.db_path)
        try:
            return conn.execute("SELECT COUNT(*) FROM session").fetchone()[0]
        finally:
            conn.close()

    def _plan_split(self) -> engine.OperationPlan:
        bundle = engine.load_bundle(self.db_path, self.meeting_hex)
        return engine.plan_split(
            bundle,
            db_path=self.db_path,
            split_ms=120000,
            tool=self.tool,
            uuid_factory=support.sequential_uuid_factory(),
            hex_suffix=support.FixedHexSuffix(),
            clock=support.FixedClock(),
            plan_root=self.plan_root,
        )


class TestIdentify(_EngineCase):
    def test_identify_ranks_meeting_by_title(self) -> None:
        """identify returns the seeded meeting for a matching title hint."""
        candidates = engine.identify(self.db_path, title="Weekly Sync")
        self.assertTrue(candidates)
        self.assertEqual(candidates[0].record.id_hex, self.meeting_hex)


class TestPlanIsDryRun(_EngineCase):
    def test_plan_writes_nothing_to_db(self) -> None:
        """Planning stages audio + emits plan.json but does not touch the DB."""
        before = self._session_count()
        op_plan = self._plan_split()
        after = self._session_count()
        self.assertEqual(before, after)  # no live writes
        self.assertEqual(len(op_plan.clone_plans), 2)
        self.assertTrue((self.plan_root / engine.PLAN_FILENAME).exists())
        # Staged audio exists in temp, not in ExternalMedia.
        staged = list(Path(op_plan.staging_dir).rglob("*.m4a"))
        self.assertTrue(staged)

    def test_plan_round_trips_to_disk(self) -> None:
        """A written plan.json reloads into an equivalent OperationPlan."""
        op_plan = self._plan_split()
        reloaded = engine.OperationPlan.read(self.plan_root / engine.PLAN_FILENAME)
        self.assertEqual(reloaded.op, "split")
        self.assertEqual(len(reloaded.clone_plans), 2)


class TestApply(_EngineCase):
    def test_apply_creates_two_sessions_and_verifies(self) -> None:
        """Apply materializes both halves, backs up first, and verifies clean."""
        op_plan = self._plan_split()
        result = engine.apply(
            op_plan,
            process_checker=support.FakeProcessChecker(False),
            clock=support.FixedClock(),
            tool=None,  # skip ffprobe-based duration check (fake tool can't model both halves)
            backup_root=self.backup_root,
        )
        self.assertTrue(result.ok, msg=result.summary())
        self.assertEqual(self._session_count(), 4)  # 2 source + 2 new

    def test_apply_takes_backup_before_writing(self) -> None:
        """A timestamped backup of main.sqlite + media is created."""
        op_plan = self._plan_split()
        result = engine.apply(
            op_plan,
            process_checker=support.FakeProcessChecker(False),
            clock=support.FixedClock(),
            tool=None,
            backup_root=self.backup_root,
        )
        self.assertTrue(Path(result.manifest.backup_dir).exists())
        self.assertTrue((Path(result.manifest.backup_dir) / "Database" / "main.sqlite").exists())
        self.assertEqual(len(result.manifest.media_backups), 5)

    def test_apply_retains_source(self) -> None:
        """The source meeting + its 5 media files survive apply (§1)."""
        op_plan = self._plan_split()
        engine.apply(
            op_plan,
            process_checker=support.FakeProcessChecker(False),
            clock=support.FixedClock(),
            tool=None,
            backup_root=self.backup_root,
        )
        conn = db.open_readonly(self.db_path)
        try:
            sid = db.hex_to_bytes(self.meeting_hex)
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM session WHERE id = ?", (sid,)).fetchone()[0], 1
            )
            n_media = conn.execute(
                "SELECT COUNT(*) FROM mediafile WHERE sessionID = ? OR recordedMeetingID = "
                "(SELECT recordedMeetingID FROM session WHERE id = ?)", (sid, sid)
            ).fetchone()[0]
            self.assertGreaterEqual(n_media, 5)
        finally:
            conn.close()

    def test_apply_writes_new_audio_files(self) -> None:
        """All new tracks land in ExternalMedia."""
        op_plan = self._plan_split()
        result = engine.apply(
            op_plan,
            process_checker=support.FakeProcessChecker(False),
            clock=support.FixedClock(),
            tool=None,
            backup_root=self.backup_root,
        )
        for clone_result in result.results:
            for path in clone_result.written_files:
                self.assertTrue(Path(path).exists())

    def test_guard_blocks_apply_when_running(self) -> None:
        """Apply refuses (no writes) when MacWhisper is running."""
        op_plan = self._plan_split()
        before = self._session_count()
        with self.assertRaises(db.MacWhisperRunningError):
            engine.apply(
                op_plan,
                process_checker=support.FakeProcessChecker(True),
                clock=support.FixedClock(),
                backup_root=self.backup_root,
            )
        self.assertEqual(self._session_count(), before)  # nothing written


class TestBackup(_EngineCase):
    def test_backup_missing_db_raises(self) -> None:
        """create_backup refuses when the database file is absent."""
        with self.assertRaises(backup.BackupError):
            backup.create_backup(
                self.tmp / "nope.sqlite", [], backup_root=self.backup_root,
                clock=support.FixedClock(),
            )

    def test_backup_then_restore_round_trip(self) -> None:
        """A backed-up file can be restored over a modified original."""
        media_file = self.external / "x.m4a"
        media_file.parent.mkdir(parents=True, exist_ok=True)
        media_file.write_bytes(b"original")
        manifest = backup.create_backup(
            self.db_path, [media_file], backup_root=self.backup_root,
            clock=support.FixedClock(),
        )
        media_file.write_bytes(b"corrupted")
        backup.restore_backup(manifest)
        self.assertEqual(media_file.read_bytes(), b"original")


if __name__ == "__main__":
    unittest.main()
