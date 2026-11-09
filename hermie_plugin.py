"""Hermes adapter: lifecycle hooks, the /hermie slash command and `hermes hermie`.

Hooks never raise: a broken pet must not interrupt the agent.
"""
from __future__ import annotations

import json

try:  # loaded by Hermes as a package
    from . import hermie as engine
    from . import hermie_cli
except ImportError:  # run from a checkout (tests, local scripts)
    import hermie as engine
    import hermie_cli


def tool_succeeded(**kwargs):
    """Did this post_tool_call describe a tool that actually ran cleanly?

    Hermes sends status "ok", "error" or "blocked". Older hosts send no
    status, so fall back to reading the result, which is usually a JSON string.
    """
    status = kwargs.get("status")
    if status is not None:
        return status == "ok"
    if kwargs.get("success") is False or kwargs.get("error_type") or kwargs.get("error_message"):
        return False
    result = kwargs.get("result")
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except ValueError:
            return True
    if isinstance(result, dict) and (result.get("error") or result.get("success") is False):
        return False
    return True


def register(ctx):
    def on_session_start(**kwargs):
        try:
            engine.observe("session_start")
        except Exception:
            pass

    def on_session_end(**kwargs):
        try:
            engine.observe("session_end")
        except Exception:
            pass

    def post_tool_call(**kwargs):
        try:
            if tool_succeeded(**kwargs):
                engine.observe("tool_completed", kwargs.get("tool_name"))
        except Exception:
            pass

    def slash(raw_args="", **kwargs):
        try:
            return engine.chat_command(raw_args)
        except Exception as exc:
            return f"🐣 Hermie hit a problem: {exc}"

    ctx.register_hook("on_session_start", on_session_start)
    ctx.register_hook("on_session_end", on_session_end)
    ctx.register_hook("post_tool_call", post_tool_call)
    if hasattr(ctx, "register_command"):
        ctx.register_command(
            "hermie",
            slash,
            description="Check on and care for your local companion",
            args_hint="status | feed | play | rest | rename NAME",
        )
    if hasattr(ctx, "register_cli_command"):
        ctx.register_cli_command(
            "hermie",
            "Check on and care for your local companion",
            hermie_cli.setup_parser,
            hermie_cli.run,
        )
