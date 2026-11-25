import os
import shutil
import tempfile
import unittest

import game as gamemod
import gamehelpers as gh
import replicate
import server
from test_server import ADMIN, ServerCase


class FollowerCase(ServerCase):
    def follower(self, **kw):
        spare = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, spare, True)
        state = os.path.join(spare, "state")
        return replicate.Follower("127.0.0.1:%d" % self.port, kw.get("password", ADMIN), state), state

    def act(self, n=3):
        for i in range(n):
            self.g.submit(1, dict(type="set_quality", mode="high" if i % 2 else "low"))


class ReplicationTests(FollowerCase):
    def test_a_pull_makes_the_copy_equal_the_primary_and_later_pulls_extend_it(self):
        f, _ = self.follower()
        self.act()
        f.pull_once()
        with open(self.g.log_path, "rb") as a, open(f.log_path, "rb") as b:
            self.assertEqual(a.read(), b.read())
        self.act(4)
        gh.advance_days(self.g, self.ft, 0)
        added, _ = f.pull_once()
        self.assertGreater(added, 0)
        with open(self.g.log_path, "rb") as a, open(f.log_path, "rb") as b:
            self.assertEqual(a.read(), b.read())
        self.assertEqual(f.pull_once()[0], 0)

    def test_a_spare_started_on_the_copied_directory_matches_every_team_and_the_board(self):
        f, state = self.follower()
        self.g.clock_op("resume")
        self.g.book(2, "cto")
        self.g.stakeholder_decline(3, 3)
        self.act()
        gh.advance_days(self.g, self.ft, 12)
        self.g.snapshot_now()
        f.pull_once()
        spare = gamemod.Game(self.g.cfg, state, now=gh.FakeTime())
        self.addCleanup(spare.close)
        self.assertEqual(gh.digests(spare), gh.digests(self.g))
        self.assertEqual(spare.stakeholder_board()["bookings"], self.g.stakeholder_board()["bookings"])
        self.assertEqual({t["team"]: t["code"] for t in spare.registry["teams"]}, self.codes)
        self.assertTrue(os.listdir(os.path.join(state, "snapshots")))
        self.assertFalse(spare.clock.status(0)["running"])

    def test_a_torn_local_tail_is_trimmed_and_the_next_pull_completes_it(self):
        f, state = self.follower()
        self.act()
        f.pull_once()
        with open(f.log_path, "ab") as fh:
            fh.write(b'{"kind":"tick","da')                  # a crash mid-write
        again = replicate.Follower("127.0.0.1:%d" % self.port, ADMIN, state)
        again.pull_once()
        with open(self.g.log_path, "rb") as a, open(again.log_path, "rb") as b:
            self.assertEqual(a.read(), b.read())

    def test_a_wrong_or_other_password_gets_the_same_401_on_all_three_routes(self):
        for headers in (None, {server.ADMIN_HEADER: "wrong"}, {server.STAKEHOLDER_HEADER: "stake-secret"}):
            seen = {self.call("GET", path, None, headers)[0] for path in (
                "/api/admin/log?offset=0", "/api/admin/registry", "/api/admin/snapshot-latest")}
            self.assertEqual(seen, {401}, headers)
        status, _ = self.call("GET", "/api/admin/registry", None, {server.ADMIN_HEADER: ADMIN})
        self.assertEqual(status, 200)

    def test_a_follower_with_the_wrong_password_stops_instead_of_writing(self):
        f, _ = self.follower(password="wrong")
        with self.assertRaises(PermissionError):
            f.pull_once()
        self.assertFalse(os.path.exists(f.log_path))

    def test_a_copy_of_a_different_game_is_refused_and_left_alone(self):
        f, _ = self.follower()
        self.act()
        f.pull_once()
        with open(f.log_path, "rb") as fh:
            held = fh.read()
        tampered = bytearray(held)
        tampered[-5] = ord("X") if tampered[-5] != ord("X") else ord("Y")
        with open(f.log_path, "wb") as fh:
            fh.write(bytes(tampered))
        self.act()
        with self.assertRaises(replicate.Diverged):
            f.pull_log()
        with open(f.log_path, "rb") as fh:
            self.assertEqual(fh.read(), bytes(tampered))

    def test_a_copy_longer_than_the_primary_log_is_refused(self):
        f, _ = self.follower()
        self.act()
        f.pull_once()
        with open(f.log_path, "ab") as fh:
            fh.write(b'{"kind":"system","op":"extra"}\n')
        with self.assertRaises(replicate.Diverged):
            f.pull_log()


class ChunkedReplicationTests(FollowerCase):
    cfg_over = dict(REPLICATE_CHUNK_BYTES=300)

    def test_a_log_larger_than_one_chunk_arrives_whole_and_only_in_whole_lines(self):
        f, _ = self.follower()
        self.act(12)
        status, body, _ = self.call("GET", "/api/admin/log?offset=0", None, {server.ADMIN_HEADER: ADMIN}, raw=True)
        self.assertEqual(status, 200)
        self.assertLess(len(body), self.g.log.size)
        self.assertTrue(body.endswith(b"\n"))
        f.pull_once()
        with open(self.g.log_path, "rb") as a, open(f.log_path, "rb") as b:
            self.assertEqual(a.read(), b.read())


if __name__ == "__main__":
    unittest.main()
