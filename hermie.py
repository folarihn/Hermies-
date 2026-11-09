"""Hermie: a local, privacy-conscious virtual companion for Hermes."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(os.environ.get("HERMIE_HOME", str(Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))) / "hermie")))
_LOCK = threading.RLock()
INITIAL = {"name": "Hermie", "xp": 0, "energy": 80, "happiness": 75, "bond": 0, "snacks": 3, "last_seen": 0, "last_tool": 0, "last_play": 0, "tasks": 0, "curiosity": 0, "craft": 0}

@contextmanager
def _connect():
    ROOT.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(ROOT / "pet.sqlite3", timeout=10)
    db.execute("CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, ts INTEGER NOT NULL, kind TEXT NOT NULL, detail TEXT NOT NULL)")
    try:
        yield db
    finally:
        db.close()

def _read(db):
    row = db.execute("SELECT value FROM state WHERE key='pet'").fetchone()
    return {**INITIAL, **json.loads(row[0])} if row else dict(INITIAL)

def _save(db, pet, kind, detail=""):
    db.execute("INSERT OR REPLACE INTO state(key,value) VALUES('pet',?)", (json.dumps(pet),))
    db.execute("INSERT INTO events(ts,kind,detail) VALUES(?,?,?)", (int(time.time()), kind, detail))
    db.commit()

def status():
    with _LOCK, _connect() as db:
        p = _read(db)
    p["level"] = 1 + p["xp"] // 50
    p["stage"] = "Hatchling" if p["level"] < 4 else "Explorer" if p["level"] < 10 else "Companion"
    p["personality"] = "Tinkerer" if p["craft"] > p["curiosity"] else "Explorer" if p["curiosity"] else "Curious"
    return p

def interact(action, name=None):
    if action not in {"feed", "play", "rest", "rename"}:
        raise ValueError("Unknown action")
    with _LOCK, _connect() as db:
        p = _read(db)
        now = int(time.time())
        if action == "rename":
            if not name or not 1 <= len(name.strip()) <= 24 or not all(c.isalnum() or c in " -_" for c in name):
                raise ValueError("Name must be 1-24 letters, numbers, spaces, - or _")
            p["name"] = name.strip()
        elif action == "feed":
            if p["snacks"] < 1:
                raise ValueError("No snacks left; earn them through activity")
            p["snacks"] -= 1
            p["energy"] = min(100, p["energy"] + 12)
            p["happiness"] = min(100, p["happiness"] + 5)
        elif action == "play":
            if now - p["last_play"] < 60:
                raise ValueError("Hermie needs a minute before playing again")
            if p["energy"] < 10:
                raise ValueError("Hermie is tired; let it rest")
            p["last_play"] = now
            p["energy"] -= 10
            p["happiness"] = min(100, p["happiness"] + 15)
            p["bond"] = min(100, p["bond"] + 4)
            p["xp"] += 4
        elif action == "rest":
            p["energy"] = min(100, p["energy"] + 20)
        _save(db, p, action)
    return status()

def observe(kind):
    if kind not in {"session_start", "session_end", "tool_completed"}:
        return
    with _LOCK, _connect() as db:
        p = _read(db)
        now = int(time.time())
        # Cooldown prevents rapid tool loops from farming infinite XP.
        if kind == "tool_completed" and now - p["last_tool"] < 20:
            return
        if kind == "tool_completed":
            p["xp"] += 3
            p["last_tool"] = now
            p["tasks"] += 1  # completed tool operations, not completed user tasks
            p["energy"] = max(0, p["energy"] - 1)
            if p["tasks"] % 5 == 0:
                p["snacks"] = min(20, p["snacks"] + 1)
        elif kind == "session_start":
            p["bond"] = min(100, p["bond"] + 1)
        p["last_seen"] = now
        _save(db, p, kind)

def chat_command(raw_args=""):
    """Lightweight local commands, with no remote calls."""
    parts = str(raw_args or "").strip().split(maxsplit=1)
    action = parts[0].lower() if parts else "status"
    try:
        pet = status() if action == "status" else interact(action, parts[1] if len(parts) > 1 else None)
        return (
            f"🐣 {pet['name']} · {pet['stage']} · Lv {pet['level']}\n"
            f"♥ Happiness {pet['happiness']} | ⚡ Energy {pet['energy']} | "
            f"✦ Bond {pet['bond']}\n"
            f"XP {pet['xp']} · 🍪 Snacks {pet['snacks']}\n"
            "Commands: /hermie status | feed | play | rest | rename NAME"
        )
    except ValueError as exc:
        return f"🐣 {exc}"

def register(ctx):
    """Hermes lifecycle adapter; failures never interrupt the agent."""
    def start(**kwargs):
        try:
            observe("session_start")
        except Exception:
            pass

    def end(**kwargs):
        try:
            observe("session_end")
        except Exception:
            pass

    def after(tool_name=None, args=None, result=None, **kwargs):
        try:
            # Match Hermes post_tool_call contract. An error or explicit false
            # means no XP. A completed hook with no error counts as an observed
            # tool completion, not proof the user's overall task succeeded.
            if kwargs.get("success") is False or kwargs.get("status") in {"error", "failed"}:
                return
            if isinstance(result, dict) and (result.get("error") or result.get("success") is False):
                return
            observe("tool_completed")
        except Exception:
            pass

    if hasattr(ctx, "register_command"):
        ctx.register_command(
            "hermie",
            lambda raw_args="": chat_command(raw_args),
            description="Play with your local virtual companion",
            args_hint="status | feed | play | rest | rename NAME",
        )
    ctx.register_hook("on_session_start", start)
    ctx.register_hook("on_session_end", end)
    ctx.register_hook("post_tool_call", after)
