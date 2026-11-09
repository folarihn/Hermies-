"""Hermes integration adapter tests, without installing Hermes itself."""
import unittest
from unittest.mock import patch
import hermie

class FakeContext:
    def __init__(self):
        self.hooks = {}
        self.commands = {}
    def register_hook(self, name, fn):
        self.hooks[name] = fn
    def register_command(self, name, fn, **kwargs):
        self.commands[name] = fn

class AdapterTests(unittest.TestCase):
    def test_registers_expected_hooks_and_chat(self):
        ctx = FakeContext()
        hermie.register(ctx)
        self.assertEqual(set(ctx.hooks), {"on_session_start","on_session_end","post_tool_call"})
        self.assertIn("hermie", ctx.commands)

    def test_failed_tool_does_not_award_xp(self):
        ctx = FakeContext()
        hermie.register(ctx)
        with patch.object(hermie, "observe") as observed:
            ctx.hooks["post_tool_call"]("shell", {}, {"error":"failed"})
            ctx.hooks["post_tool_call"]("shell", {}, {"success":False})
            ctx.hooks["post_tool_call"]("shell", {}, None, success=False)
            observed.assert_not_called()

    def test_completed_tool_is_observed(self):
        ctx = FakeContext()
        hermie.register(ctx)
        with patch.object(hermie, "observe") as observed:
            ctx.hooks["post_tool_call"]("shell", {}, {"success":True})
            observed.assert_called_once_with("tool_completed")

if __name__ == "__main__":
    unittest.main()
