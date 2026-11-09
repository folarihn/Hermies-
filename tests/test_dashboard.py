"""Dashboard tab: backend routes, manifest, bundle freshness and sprite shape."""
import importlib.util
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = patch.dict(os.environ, {"HERMIE_HOME": self.tmp.name})
        env.start()
        self.addCleanup(env.stop)
        # Hermes imports plugin_api.py by path, outside any package: do the same.
        self.api = load("hermie_test_plugin_api", "dashboard/plugin_api.py")
        self.addCleanup(sys.modules.pop, "hermie_dashboard_engine", None)

    def test_routes_work_when_loaded_by_path(self):
        self.assertTrue(hasattr(self.api, "router"))
        self.assertEqual(self.api.get_pet()["name"], "Hermie")
        pet = self.api.post_action({"action": "rename", "name": "Pixel"})
        self.assertEqual((pet["name"], pet["recent"][0]["kind"]), ("Pixel", "rename"))

    def test_bad_action_is_a_400(self):
        for payload in ({"action": "nope"}, {"action": "rename", "name": 7}, "feed"):
            with self.assertRaises(self.api.HTTPException) as caught:
                self.api.post_action(payload)
            self.assertEqual(caught.exception.status_code, 400)

    def test_manifest_points_at_real_files(self):
        manifest = json.loads((ROOT / "dashboard/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "hermie")
        for key in ("entry", "css", "api"):
            self.assertTrue((ROOT / "dashboard" / manifest[key]).is_file(), key)

    def test_versions_agree(self):
        import hermie
        manifest = json.loads((ROOT / "dashboard/manifest.json").read_text(encoding="utf-8"))
        plugin = (ROOT / "plugin.yaml").read_text(encoding="utf-8")
        self.assertEqual(manifest["version"], hermie.VERSION)
        self.assertIn('version: "%s"' % hermie.VERSION, plugin)

    def test_bundle_is_up_to_date(self):
        build = load("hermie_test_build", "tools/build_dashboard.py")
        self.assertEqual(build.main(["--check"]), 0, "run python tools/build_dashboard.py")

    def test_sprites_are_16_by_16(self):
        source = (ROOT / "web/hermie-view.js").read_text(encoding="utf-8")
        rows = re.findall(r'^\s+"([.a-z]+)",$', source, re.M)
        self.assertEqual(len(rows), 3 * 16)
        self.assertEqual({len(row) for row in rows}, {16})


if __name__ == "__main__":
    unittest.main()
