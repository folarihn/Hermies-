"""Hermes adapter tests against the real hook contract, without Hermes installed."""
import argparse
import unittest
from unittest.mock import patch

import hermie
import hermie_plugin


class FakeContext:
    def __init__(self):
        self.hooks, self.commands, self.cli = {}, {}, {}

    def register_hook(self, name, fn):
        self.hooks[name] = fn

    def register_command(self, name, handler, description="", args_hint=""):
        self.commands[name] = handler

    def register_cli_command(self, name, help, setup_fn, handler_fn=None, description=""):
        self.cli[name] = (setup_fn, handler_fn)


class HooksOnlyContext:
    """An older host with hooks but no command registration."""
    def __init__(self):
        self.hooks = {}

    def register_hook(self, name, fn):
        self.hooks[name] = fn


# What Hermes 0.20 passes to post_tool_call, minus the ids.
def tool_event(**overrides):
    event = {"tool_name": "terminal", "args": {"command": "ls"}, "result": '{"output": "ok"}',
             "task_id": "", "session_id": "s1", "duration_ms": 12, "status": "ok",
             "error_type": None, "error_message": None, "middleware_trace": [],
             "telemetry_schema_version": "hermes.observer.v1"}
    event.update(overrides)
    return event


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.ctx = FakeContext()
        hermie_plugin.register(self.ctx)

    def test_registers_hooks_and_commands(self):
        self.assertEqual(set(self.ctx.hooks), {"on_session_start", "on_session_end", "post_tool_call"})
        self.assertIn("hermie", self.ctx.commands)
        self.assertIn("hermie", self.ctx.cli)

    def test_works_on_a_host_without_commands(self):
        ctx = HooksOnlyContext()
        hermie_plugin.register(ctx)
        self.assertEqual(len(ctx.hooks), 3)

    def test_ok_tool_is_observed_with_its_name(self):
        with patch.object(hermie, "observe") as observed:
            self.ctx.hooks["post_tool_call"](**tool_event())
            observed.assert_called_once_with("tool_completed", "terminal")

    def test_error_and_blocked_tools_earn_nothing(self):
        with patch.object(hermie, "observe") as observed:
            self.ctx.hooks["post_tool_call"](**tool_event(status="error", error_type="tool_error"))
            self.ctx.hooks["post_tool_call"](**tool_event(status="blocked"))
            observed.assert_not_called()

    def test_host_without_status_falls_back_to_the_result(self):
        legacy = lambda **kw: {k: v for k, v in tool_event(**kw).items() if k != "status"}
        self.assertTrue(hermie_plugin.tool_succeeded(**legacy()))
        self.assertTrue(hermie_plugin.tool_succeeded(**legacy(result="plain text output")))
        self.assertFalse(hermie_plugin.tool_succeeded(**legacy(result='{"error": "boom"}')))
        self.assertFalse(hermie_plugin.tool_succeeded(**legacy(result={"success": False})))
        self.assertFalse(hermie_plugin.tool_succeeded(**legacy(error_message="boom")))

    def test_hooks_never_raise(self):
        with patch.object(hermie, "observe", side_effect=RuntimeError("disk full")):
            self.ctx.hooks["post_tool_call"](**tool_event())
            self.ctx.hooks["on_session_start"](session_id="s1", model="m", platform="cli")
            self.ctx.hooks["on_session_end"](session_id="s1", completed=True)

    def test_slash_command_returns_text(self):
        with patch.object(hermie, "chat_command", return_value="hi") as chat:
            self.assertEqual(self.ctx.commands["hermie"]("feed", session_id="s1"), "hi")
            chat.assert_called_once_with("feed")

    def test_cli_parser_setup(self):
        setup, handler = self.ctx.cli["hermie"]
        parser = argparse.ArgumentParser()
        setup(parser)
        self.assertEqual(parser.parse_args([]).action, "status")
        args = parser.parse_args(["rename", "Pixel", "--json"])
        self.assertEqual((args.action, args.name, args.json), ("rename", "Pixel", True))
        self.assertTrue(callable(handler))


if __name__ == "__main__":
    unittest.main()
