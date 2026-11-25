"""The failure drill, scaled down: real server processes, killed and restarted."""
import unittest

import helpers  # noqa: F401  (puts the project root on sys.path)
import drill


def failures(rows):
    return [(r["scenario"], r["case"], r["detail"]) for r in rows if not r["ok"]]


class DrillTests(unittest.TestCase):
    def test_hard_kills_at_three_points_lose_nothing_and_the_game_carries_on(self):
        rows = drill.scenario_kill(3)
        self.assertEqual([r["case"] for r in rows], ["mid-quarter", "checkpoint pause", "action burst"])
        self.assertEqual(failures(rows), [])

    def test_a_spare_started_from_the_followers_copy_loses_only_what_came_after_the_last_pull(self):
        self.assertEqual(failures(drill.scenario_spare(3)), [])

    def test_a_game_restarts_from_a_bare_snapshot_and_runs_on(self):
        self.assertEqual(failures(drill.scenario_snapshot(3)), [])

    def test_a_longer_log_restarts_inside_the_bar(self):
        row = drill.scenario_long_log(3, 60)
        self.assertTrue(row["ok"], row["detail"])
        self.assertLess(row["seconds"], drill.RECOVERY_BAR_SECONDS)

    def test_a_missing_acknowledged_action_is_reported_as_lost(self):
        import json
        import os
        import shutil
        import tempfile
        import config
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        with open(os.path.join(d, config.LOG_FILE), "w", encoding="utf-8") as f:
            f.write(json.dumps(dict(kind="action", seq=1, day=0, team=1, source="team",
                                    action=dict(type="set_quality", mode="low"))) + "\n")
        have = drill.key(dict(type="set_quality", mode="low"))
        gone = drill.key(dict(type="set_quality", mode="high"))
        lost = drill.lost_actions([(1, have, 1.0), (1, gone, 2.0), (1, have, 3.0)], d)
        self.assertEqual([(t, k) for t, k, _ in lost], [(1, gone), (1, have)])


if __name__ == "__main__":
    unittest.main()
