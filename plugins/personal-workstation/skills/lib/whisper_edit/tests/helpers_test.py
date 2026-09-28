"""Unit tests for the low-level helpers: db, media, selection, model utils."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import support  # noqa: E402  (adds LIB_ROOT to sys.path)

from whisper_edit import db, media, model, selection
from whisper_edit.selection import SessionRecord


class TestUuidHexConventions(unittest.TestCase):
    """BLOB-UUID <-> hex <-> canonical projections (spec §3.1)."""

    def test_hex_round_trips_through_bytes(self) -> None:
        """A 16-byte id survives hex -> bytes -> hex unchanged."""
        raw = db.new_uuid_bytes()
        hex_str = db.to_hex(raw)
        self.assertEqual(len(hex_str), 32)
        self.assertEqual(db.hex_to_bytes(hex_str), raw)

    def test_canonical_uuid_is_uppercase_dashed(self) -> None:
        """The filename prefix form is uppercase 8-4-4-4-12."""
        raw = bytes.fromhex("a1b2c3d40000400080000000000000ff")
        canonical = db.bytes_to_canonical_uuid(raw)
        self.assertEqual(canonical, "A1B2C3D4-0000-4000-8000-0000000000FF")
        self.assertEqual(db.hex_to_canonical_uuid(raw.hex()), canonical)

    def test_to_hex_passthrough_and_none(self) -> None:
        """to_hex lowercases str input and passes None through."""
        self.assertIsNone(db.to_hex(None))
        self.assertEqual(db.to_hex("ABCD"), "abcd")


class TestTimeModel(unittest.TestCase):
    """UTC string parsing/formatting and Mac-absolute-time conversion (§3.2)."""

    def test_parses_both_datetime_forms(self) -> None:
        """Both millisecond and second forms (and a T separator) parse."""
        a = db.parse_db_datetime("2026-05-30 16:00:00.250")
        b = db.parse_db_datetime("2026-05-30 16:00:00")
        c = db.parse_db_datetime("2026-05-30T16:00:00.250")
        self.assertEqual(a.year, 2026)
        self.assertEqual(b.minute, 0)
        self.assertEqual(a, c)

    def test_format_emits_millisecond_utc(self) -> None:
        """Formatting yields 'YYYY-MM-DD HH:MM:SS.fff'."""
        dt = db.parse_db_datetime("2026-05-30 16:00:00.250")
        self.assertEqual(db.format_db_datetime(dt), "2026-05-30 16:00:00.250")

    def test_mac_absolute_round_trip(self) -> None:
        """Mac-absolute <-> Unix conversion is reversible."""
        self.assertAlmostEqual(db.mac_absolute_to_unix(0.0), 978307200.0)
        self.assertAlmostEqual(db.unix_to_mac_absolute(978307200.0), 0.0)


class TestGuardedOpen(unittest.TestCase):
    """The read-write guard (spec §1) is enforced in code."""

    def test_refuses_to_open_while_macwhisper_running(self) -> None:
        """open_readwrite raises when the process checker reports running."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "main.sqlite"
            support.make_db_file(path)
            with self.assertRaises(db.MacWhisperRunningError):
                db.open_readwrite(path, process_checker=support.FakeProcessChecker(True))

    def test_opens_when_not_running(self) -> None:
        """open_readwrite succeeds when the checker reports not running."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "main.sqlite"
            support.make_db_file(path)
            conn = db.open_readwrite(path, process_checker=support.FakeProcessChecker(False))
            try:
                self.assertEqual(conn.execute("SELECT 1").fetchone()[0], 1)
            finally:
                conn.close()


class TestSchemaDrift(unittest.TestCase):
    """PRAGMA table_info-based column resolution (§8)."""

    def test_resolves_model_column_typo(self) -> None:
        """The misspelled `modelIdentifer` is resolved over the correct spelling."""
        self.assertEqual(db.resolve_model_column({"modelIdentifer"}), "modelIdentifer")
        self.assertEqual(db.resolve_model_column({"modelIdentifier"}), "modelIdentifier")
        self.assertIsNone(db.resolve_model_column({"other"}))

    def test_insertable_columns_drops_unknown(self) -> None:
        """insertable_columns omits columns the live schema lacks."""
        conn = db.open_in_memory()
        support.build_schema(conn, with_fts=False)
        row = {"id": b"x", "filename": "f.m4a", "type": "original", "nonexistent": 1}
        filtered = db.insertable_columns(conn, "mediafile", row)
        self.assertNotIn("nonexistent", filtered)
        self.assertIn("filename", filtered)


class TestMediaFilenames(unittest.TestCase):
    """Filename grammar + 8-hex suffix strategies (§7.1, §10.1)."""

    def test_make_filename_matches_grammar(self) -> None:
        """make_media_filename composes <UUID>_<token>_<8HEX>.<ext>."""
        name = media.make_media_filename(
            "A1B2C3D4-0000-4000-8000-000000000000", "track-0", "DEADBEEF"
        )
        self.assertEqual(name, "A1B2C3D4-0000-4000-8000-000000000000_track-0_DEADBEEF.m4a")
        self.assertEqual(model.parse_filename_token(name), "track-0")

    def test_random_suffix_is_eight_hex(self) -> None:
        """The default suffix is 8 uppercase hex chars."""
        suffix = media.RandomHexSuffix().derive()
        self.assertEqual(len(suffix), 8)
        self.assertEqual(suffix, suffix.upper())
        int(suffix, 16)  # parses as hex

    def test_move_refuses_path_traversal(self) -> None:
        """move_into_external_media rejects a filename escaping the media dir."""
        with tempfile.TemporaryDirectory() as tmp:
            ext = Path(tmp) / "ExternalMedia"
            ext.mkdir()
            staged = Path(tmp) / "staged.m4a"
            staged.write_bytes(b"x")
            with self.assertRaises(media.MediaError):
                media.move_into_external_media(staged, ext, "../escape.m4a")


class TestMediaStaging(unittest.TestCase):
    """Staging cuts/concats via an injected fake tool (no ffmpeg)."""

    def test_single_cut_stages_and_probes(self) -> None:
        """A one-cut target produces one file with the probed duration."""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src.m4a"
            src.write_bytes(b"audio")
            ta = model.TargetAudio(
                media_type="multitrackItem", track_token="track-0",
                owner=model.OwnerKind.SESSION,
                cuts=(model.AudioCut(source_path=src, start_ms=0, end_ms=5000),),
            )
            tool = support.FakeMediaTool(duration_ms=4800)
            staged = media.stage_target_audio(ta, tool=tool, work_dir=Path(tmp) / "stage", index=0)
            self.assertTrue(staged.path.exists())
            self.assertEqual(staged.duration_ms, 4800)
            self.assertEqual(len(tool.cut_calls), 1)

    def test_multi_cut_concats(self) -> None:
        """A multi-cut target trims each part then concatenates."""
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "a.m4a"; a.write_bytes(b"a")
            b = Path(tmp) / "b.m4a"; b.write_bytes(b"b")
            ta = model.TargetAudio(
                media_type="multitrackItem", track_token="track-0",
                owner=model.OwnerKind.SESSION,
                cuts=(
                    model.AudioCut(source_path=a, start_ms=0, end_ms=None),
                    model.AudioCut(source_path=b, start_ms=0, end_ms=None),
                ),
            )
            tool = support.FakeMediaTool()
            staged = media.stage_target_audio(ta, tool=tool, work_dir=Path(tmp) / "stage", index=0)
            self.assertTrue(staged.path.exists())
            self.assertEqual(len(tool.concat_calls), 1)


class TestWordsJsonShift(unittest.TestCase):
    """Per-word ms timings shift with the line (§5.2)."""

    def test_shifts_word_times(self) -> None:
        """A positive delta moves both startTime and endTime."""
        payload = '[{"text":"hi","startTime":1000,"endTime":1500}]'
        shifted = model.shift_words_json(payload, 500)
        self.assertIn('"startTime":1500', shifted)
        self.assertIn('"endTime":2000', shifted)

    def test_zero_delta_is_identity(self) -> None:
        """A zero delta passes the original payload through."""
        payload = '[{"text":"hi","startTime":0,"endTime":1}]'
        self.assertEqual(model.shift_words_json(payload, 0), payload)

    def test_malformed_payload_drops_to_none(self) -> None:
        """Unparseable word JSON is dropped rather than corrupted."""
        self.assertIsNone(model.shift_words_json("not json", 100))
        self.assertIsNone(model.shift_words_json(None, 100))


class TestSelectionRanking(unittest.TestCase):
    """Pure candidate ranking (no IO)."""

    def _records(self) -> list[SessionRecord]:
        return [
            SessionRecord("aa", "Weekly Sync", "2026-05-30 16:00:00.000", "meeting"),
            SessionRecord("bb", "Lunch chat", "2026-05-29 12:00:00.000", "meeting"),
            SessionRecord("cc", "Weekly Sync Redux", "2026-05-30 16:30:00.000", "meeting"),
        ]

    def test_title_match_ranks_first(self) -> None:
        """An exact substring title hit outranks a weaker fuzzy match."""
        ranked = selection.rank_candidates(self._records(), title="Weekly Sync")
        self.assertEqual(ranked[0].record.id_hex, "aa")

    def test_date_boost_applies(self) -> None:
        """A same-day hint contributes a 'same-day' reason."""
        ranked = selection.rank_candidates(self._records(), title="weekly", date="2026-05-30")
        self.assertIn("same-day", ranked[0].reasons)

    def test_no_hints_returns_all_newest_first(self) -> None:
        """With no hints, everything is returned newest-first."""
        ranked = selection.rank_candidates(self._records())
        self.assertEqual(len(ranked), 3)
        self.assertEqual(ranked[0].record.id_hex, "cc")  # 16:30 is newest


if __name__ == "__main__":
    unittest.main()
