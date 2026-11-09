import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

class HermieTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.environ.get("HERMIE_HOME")
        os.environ["HERMIE_HOME"] = self.tmp.name
        import hermie
        hermie.ROOT = Path(self.tmp.name)
        self.pet = hermie

    def tearDown(self):
        if self.old is None:
            os.environ.pop("HERMIE_HOME", None)
        else:
            os.environ["HERMIE_HOME"] = self.old
        self.tmp.cleanup()

    def test_initial_state(self):
        self.assertEqual(self.pet.status()["stage"], "Hatchling")

    def test_feed_persists(self):
        before = self.pet.status()
        after = self.pet.interact("feed")
        self.assertEqual(after["snacks"], before["snacks"] - 1)
        self.assertGreaterEqual(after["energy"], before["energy"])

    def test_play_cooldown(self):
        self.pet.interact("play")
        with self.assertRaises(ValueError):
            self.pet.interact("play")

    def test_rename_validation(self):
        with self.assertRaises(ValueError):
            self.pet.interact("rename", "../secret")
        self.assertEqual(self.pet.interact("rename", "Pixel")["name"], "Pixel")

    def test_tool_observation_cooldown(self):
        self.pet.observe("tool_completed")
        first = self.pet.status()["xp"]
        self.pet.observe("tool_completed")
        self.assertEqual(first, self.pet.status()["xp"])

if __name__ == "__main__":
    unittest.main()
