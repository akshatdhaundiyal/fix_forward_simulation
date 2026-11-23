import os
import shutil
import tempfile
import unittest
from unittest import mock

import helpers  # noqa: F401  (puts the project on the path)
import store


def write_bytes(path, data):
    with open(path, "wb") as f:
        f.write(data)


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)


class EventLogTests(TempDirCase):
    def test_append_then_read_back_in_order(self):
        log = store.EventLog(os.path.join(self.dir, "e.jsonl"), fsync=False)
        log.open()
        for i in range(1000):
            self.assertEqual(log.append(dict(kind="x", n=i)), i + 1)
        log.close()
        again = store.EventLog(os.path.join(self.dir, "e.jsonl"), fsync=False)
        self.addCleanup(again.close)
        events = again.open()
        self.assertEqual([e["seq"] for e in events], list(range(1, 1001)))
        self.assertEqual(again.append(dict(kind="x")), 1001)

    def test_torn_final_line_is_dropped_and_truncated_before_appending(self):
        path = os.path.join(self.dir, "e.jsonl")
        log = store.EventLog(path, fsync=False)
        log.open()
        log.append(dict(kind="a"))
        log.append(dict(kind="b"))
        log.close()
        with open(path, "ab") as f:
            f.write(b'{"kind":"c","seq":3,"half')
        again = store.EventLog(path, fsync=False)
        events = again.open()
        self.assertEqual([e["kind"] for e in events], ["a", "b"])
        again.append(dict(kind="d"))
        again.close()
        events, _ = store.read_events(path)
        self.assertEqual([e["kind"] for e in events], ["a", "b", "d"])
        self.assertEqual([e["seq"] for e in events], [1, 2, 3])

    def test_a_log_cut_at_every_byte_reads_back_to_the_last_complete_line(self):
        path = os.path.join(self.dir, "e.jsonl")
        log = store.EventLog(path, fsync=False)
        log.open()
        for i in range(5):
            log.append(dict(kind="x", n=i))
        log.close()
        data = read_bytes(path)
        ends = [i + 1 for i, b in enumerate(data) if b == 10]
        cut_path = os.path.join(self.dir, "cut.jsonl")
        for cut in range(len(data) + 1):
            write_bytes(cut_path, data[:cut])
            events, good = store.read_events(cut_path)
            self.assertEqual(len(events), len([e for e in ends if e <= cut]))
            self.assertLessEqual(good, cut)

    def test_a_bad_line_in_the_middle_is_corruption_not_a_torn_tail(self):
        path = os.path.join(self.dir, "e.jsonl")
        open(path, "wb").write(b'{"seq":1}\nnot json\n{"seq":3}\n')
        with self.assertRaises(store.CorruptLog):
            store.read_events(path)

    def test_rewind_drops_lines_above_the_marker_but_keeps_later_lines(self):
        events = [dict(seq=i, kind="x") for i in range(1, 51)]
        events.append(dict(seq=51, kind="system", op="rewind", to_seq=40))
        events.append(dict(seq=52, kind="x"))
        eff = store.effective_events(events)
        self.assertEqual([e["seq"] for e in eff], list(range(1, 41)) + [52])

    def test_a_write_failure_surfaces_and_leaves_no_fragment(self):
        path = os.path.join(self.dir, "e.jsonl")
        log = store.EventLog(path, fsync=True)
        log.open()
        log.append(dict(kind="a"))
        with mock.patch("store.os.fsync", side_effect=OSError("disk full")):
            with self.assertRaises(store.LogWriteError):
                log.append(dict(kind="b"))
        self.assertEqual(log.seq, 1)
        log.append(dict(kind="c"))
        log.close()
        events, _ = store.read_events(path)
        self.assertEqual([e["kind"] for e in events], ["a", "c"])


class SnapshotTests(TempDirCase):
    def make(self, keep=3, retries=3):
        return store.SnapshotStore(os.path.join(self.dir, "snaps"), keep, retries, 0.0, 7)

    def test_write_and_read_round_trip(self):
        s = self.make()
        sid = s.write(5, 10, '{"seq":5,"day":10,"digest":"abc"}')
        self.assertEqual(s.read(sid)["digest"], "abc")
        self.assertEqual([e["id"] for e in s.list()], [sid])

    def test_blocked_swap_is_retried_and_then_succeeds(self):
        s = self.make()
        real = os.replace
        calls = {"n": 0}

        def flaky(a, b):
            calls["n"] += 1
            if calls["n"] < 3:
                raise PermissionError("in use")
            return real(a, b)

        with mock.patch("store.os.replace", side_effect=flaky):
            sid = s.write(1, 1, '{"seq":1}')
        self.assertEqual(calls["n"], 3)
        self.assertIsNotNone(s.read(sid))

    def test_a_swap_that_never_succeeds_raises_and_keeps_the_old_snapshot(self):
        s = self.make()
        old = s.write(1, 1, '{"seq":1,"digest":"old"}')
        with mock.patch("store.os.replace", side_effect=PermissionError("in use")):
            with self.assertRaises(store.SnapshotError):
                s.write(2, 2, '{"seq":2}')
        self.assertEqual(s.read(old)["digest"], "old")
        self.assertEqual(len(s.list()), 1)
        self.assertFalse([n for n in os.listdir(s.dir) if n.endswith(".tmp")])

    def test_retention_keeps_recent_plus_first_of_each_week(self):
        s = self.make(keep=3)
        for seq, day in [(1, 0), (2, 1), (3, 6), (4, 7), (5, 8), (6, 14), (7, 15), (8, 16), (9, 17)]:
            s.write(seq, day, '{"seq":%d}' % seq)
        kept = sorted(e["seq"] for e in s.list())
        self.assertEqual(kept, [1, 4, 6, 7, 8, 9])

    def test_snapshot_ids_cannot_escape_the_directory(self):
        s = self.make()
        self.assertIsNone(s.read("../../etc/passwd"))
        self.assertIsNone(s.read("snap-1-d1/../../x"))


class RegistryTests(TempDirCase):
    def test_codes_are_unique_six_characters_and_survive_a_restart(self):
        path = os.path.join(self.dir, "teams.json")
        a = store.load_or_create_registry(path, 16, "ABCDEFGHJKLMNPQRSTUVWXYZ23456789", 6)
        codes = [t["code"] for t in a["teams"]]
        self.assertEqual(len(set(codes)), 16)
        self.assertTrue(all(len(c) == 6 for c in codes))
        b = store.load_or_create_registry(path, 16, "ABC", 6)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
