"""Pet engine rules, on a temp database with a controllable clock."""
import os
import tempfile
import unittest
from unittest.mock import patch

import hermie

HOUR = 3600


class EngineCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = patch.dict(os.environ, {"HERMIE_HOME": self.tmp.name})
        env.start()
        self.addCleanup(env.stop)
        self.now = 1_800_000_000.0
        clock = patch.object(hermie, "_now", lambda: self.now)
        clock.start()
        self.addCleanup(clock.stop)

    def wait(self, seconds):
        self.now += seconds


class BasicsTests(EngineCase):
    def test_initial_state(self):
        pet = hermie.status()
        self.assertEqual((pet["stage"], pet["level"], pet["personality"]), ("Hatchling", 1, "Curious"))
        self.assertEqual(pet["version"], hermie.VERSION)

    def test_status_does_not_write(self):
        hermie.status()
        self.assertEqual(hermie.recent(), [])

    def test_unknown_action(self):
        with self.assertRaises(ValueError):
            hermie.interact("explode")

    def test_rename_validation(self):
        for bad in ("../secret", "", "   ", "x" * 25, None, 5, ["a"]):
            with self.assertRaises(ValueError, msg=repr(bad)):
                hermie.interact("rename", bad)
        self.assertEqual(hermie.interact("rename", "  Pixel 2 ")["name"], "Pixel 2")

    def test_state_persists(self):
        hermie.interact("rename", "Pixel")
        self.assertEqual(hermie.status()["name"], "Pixel")

    def test_pre_0_3_state_is_upgraded(self):
        with hermie._txn() as db:
            db.execute("INSERT INTO state(key,value) VALUES('pet',?)",
                       ('{"name": "Old", "xp": 60, "energy": 50, "junk": 1}',))
        pet = hermie.status()
        self.assertEqual((pet["name"], pet["level"], pet["energy"], pet["fullness"]), ("Old", 2, 50, 70))


class CareTests(EngineCase):
    def test_feed_uses_a_snack_and_fills(self):
        before = hermie.status()
        after = hermie.interact("feed")
        self.assertEqual(after["snacks"], before["snacks"] - 1)
        self.assertEqual(after["fullness"], before["fullness"] + 25)

    def test_cannot_feed_when_full_or_out_of_snacks(self):
        hermie.interact("feed")  # 70 -> 95: full
        with self.assertRaisesRegex(ValueError, "full"):
            hermie.interact("feed")
        self.wait(30 * HOUR)
        hermie.interact("feed")
        hermie.interact("feed")
        with self.assertRaisesRegex(ValueError, "snacks"):
            hermie.interact("feed")

    def test_play_cooldown(self):
        hermie.interact("play")
        self.assertEqual(hermie.status()["cooldowns"]["play"], 60)
        with self.assertRaises(ValueError):
            hermie.interact("play")
        self.wait(61)
        hermie.interact("play")

    def test_rested_pet_refuses_a_nap(self):
        hermie.observe("session_end")
        self.wait(10 * HOUR)  # energy regenerates to 100
        with self.assertRaisesRegex(ValueError, "tired"):
            hermie.interact("rest")

    def test_rest_restores_energy_once(self):
        for _ in range(3):
            hermie.interact("play")
            self.wait(61)
        energy = hermie.status()["energy"]
        self.assertEqual(hermie.interact("rest")["energy"], energy + 30)
        hermie.interact("play")
        with self.assertRaisesRegex(ValueError, "nap"):
            hermie.interact("rest")


class DecayTests(EngineCase):
    def start_clock(self):
        hermie.observe("session_end")  # first write starts the needs clock

    def test_needs_change_while_away(self):
        self.start_clock()
        before = hermie.status()
        self.wait(5 * HOUR)
        after = hermie.status()
        self.assertEqual(after["fullness"], before["fullness"] - 20)
        self.assertEqual(after["happiness"], before["happiness"] - 10)
        self.assertEqual(after["energy"], min(100, before["energy"] + 15))

    def test_long_absence_is_capped_and_never_negative(self):
        self.start_clock()
        self.wait(400 * HOUR)
        pet = hermie.status()
        self.assertEqual((pet["fullness"], pet["happiness"], pet["energy"]), (0, 0, 100))
        self.assertEqual(pet["mood"], "hungry")

    def test_hungry_pet_earns_half_xp(self):
        self.start_clock()
        self.wait(20 * HOUR)  # fullness 70 -> 0
        hermie.observe("tool_completed", "terminal")
        self.assertEqual(hermie.status()["xp"], 2)


class ActivityTests(EngineCase):
    def test_tool_cooldown_survives_session_events(self):
        hermie.observe("tool_completed", "terminal")
        hermie.observe("session_start")
        hermie.observe("tool_completed", "terminal")
        self.assertEqual((hermie.status()["xp"], hermie.status()["tasks"]), (3, 1))
        self.wait(21)
        hermie.observe("tool_completed", "terminal")
        self.assertEqual(hermie.status()["xp"], 6)

    def test_unknown_event_is_ignored(self):
        hermie.observe("nonsense")
        self.assertEqual(hermie.recent(), [])

    def test_snack_every_five_tools(self):
        for _ in range(5):
            hermie.observe("tool_completed")
            self.wait(21)
        self.assertEqual(hermie.status()["snacks"], 4)

    def test_personality_follows_tool_use(self):
        for _ in range(10):
            hermie.observe("tool_completed", "web_search")
            self.wait(21)
        self.assertEqual(hermie.status()["personality"], "Scholar")
        for _ in range(11):
            hermie.observe("tool_completed", "terminal")
            self.wait(21)
        self.assertEqual(hermie.status()["personality"], "Tinkerer")

    def test_level_curve_and_level_up_event(self):
        self.assertEqual([hermie.level_for(x) for x in (0, 49, 50, 149, 150, 300)], [1, 1, 2, 2, 3, 4])
        for _ in range(17):  # 17 * 3 = 51 XP
            hermie.observe("tool_completed")
            self.wait(21)
        pet = hermie.status()
        self.assertEqual((pet["level"], pet["xp_into_level"], pet["xp_for_level"]), (2, 1, 100))
        self.assertIn({"kind": "level_up", "detail": "2"},
                      [{"kind": e["kind"], "detail": e["detail"]} for e in hermie.recent(50)])

    def test_daily_streak(self):
        hermie.observe("session_start")
        self.assertEqual(hermie.status()["streak"], 1)
        hermie.observe("session_start")  # same day: no change
        self.assertEqual(hermie.status()["streak"], 1)
        self.wait(24 * HOUR)
        hermie.observe("session_start")
        self.assertEqual(hermie.status()["streak"], 2)
        self.wait(72 * HOUR)
        hermie.observe("session_start")
        self.assertEqual(hermie.status()["streak"], 1)

    def test_event_log_is_pruned(self):
        with patch.object(hermie, "MAX_EVENTS", 10):
            for _ in range(25):
                hermie.observe("session_end")
        self.assertEqual(len(hermie.recent(1000)), 10)

    def test_chat_command(self):
        self.assertIn("Hermie · Hatchling · Lv 1", hermie.chat_command(""))
        self.assertIn("Pixel", hermie.chat_command("rename Pixel"))
        self.assertTrue(hermie.chat_command("dance").startswith("🐣 Unknown action"))


if __name__ == "__main__":
    unittest.main()
