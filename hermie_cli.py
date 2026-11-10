"""Hermie from a terminal.

Inside Hermes:      hermes hermie [status|quiet|chatty|rename NAME|feed|play|rest|log|web]
From a checkout:    python hermie_cli.py [same arguments]
"""
from __future__ import annotations

import argparse
import json
import sys
import time

try:
    from . import hermie as engine
except ImportError:
    import hermie as engine

_LABELS = {
    "feed": "Had a snack",
    "play": "Played together",
    "rest": "Took a nap",
    "rename": "Got a new name",
    "ate": "Helped itself to a snack",
    "napped": "Dozed off for a nap",
    "quiet": "Went quiet",
    "chatty": "Got chatty again",
    "tool_completed": "Watched a tool finish",
    "session_start": "Session started",
    "session_end": "Session ended",
    "level_up": "Reached level {}",
    "new_day": "Day {} of the streak",
}


def setup_parser(parser):
    parser.add_argument("action", nargs="?", default="status",
                        choices=["status", "feed", "play", "rest", "rename", "quiet", "chatty", "log", "web"])
    parser.add_argument("name", nargs="?", help="new name, for rename")
    parser.add_argument("--json", action="store_true", help="print raw JSON")
    parser.add_argument("--port", type=int, default=None, help="port for the web home")


def _say(text):
    try:  # Windows consoles default to a legacy code page that mangles the icons
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    print(text)


def run(args):
    if args.action == "web":
        try:
            from . import hermie_web
        except ImportError:
            import hermie_web
        hermie_web.main(args.port)
        return 0
    try:
        if args.action == "log":
            events = engine.recent(20)
            if args.json:
                _say(json.dumps(events, indent=2))
            for event in events if not args.json else []:
                when = time.strftime("%b %d %H:%M", time.localtime(event["ts"]))
                _say(f"{when}  {_LABELS.get(event['kind'], event['kind']).format(event['detail'])}")
            return 0
        pet = engine.status() if args.action == "status" else engine.interact(args.action, args.name)
    except ValueError as exc:
        _say(f"Hermie: {exc}")
        return 1
    _say(json.dumps(pet, indent=2) if args.json else engine.format_status(pet))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="hermie", description="Hermie virtual companion")
    setup_parser(parser)
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
