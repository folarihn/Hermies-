"""Hermie pet engine: local state, time-based needs and activity rewards.

Everything here is local. No network calls, no telemetry, and no chat text,
tool arguments or tool output is ever stored: only counters and event kinds.
"""
from __future__ import annotations

import json
import math
import os
import random
import sqlite3
import time
from contextlib import contextmanager
from datetime import date
from pathlib import Path

VERSION = "0.4.0"
ACTIONS = ("feed", "play", "rest", "rename", "quiet", "chatty")

# Needs change slowly while you are away. Nothing ever dies; a neglected pet
# is just hungry and glum, and earns XP at half speed until cared for.
FULLNESS_PER_HOUR = 4.0   # full -> empty in about a day
HAPPINESS_PER_HOUR = 2.0  # doubled while the pet is starving
ENERGY_PER_HOUR = 3.0     # energy comes back on its own
MAX_AWAY_SECONDS = 72 * 3600

TOOL_COOLDOWN = 20
PLAY_COOLDOWN = 60
REST_COOLDOWN = 600
SESSION_COOLDOWN = 600
MAX_SNACKS = 20
MAX_EVENTS = 200

# Hermie looks after itself: it lives off the agent's activity, raids the
# snack jar when hungry and naps when tired. Nobody has to press anything.
TOOL_FULLNESS = 5
TOOL_HAPPINESS = 2
HUNGRY_BELOW = 40
TIRED_BELOW = 20

# How often Hermie speaks up unprompted. Milestones always get said.
CHATTER_COOLDOWN = 45 * 60   # to you, appended to a reply
CHATTER_CHANCE = 0.35
WHISPER_COOLDOWN = 3 * 3600  # to the agent, as a short aside
MAX_QUEUED_LINES = 3

INITIAL = {
    "name": "Hermie",
    "xp": 0,
    "energy": 80.0,
    "happiness": 75.0,
    "fullness": 70.0,
    "bond": 0,
    "snacks": 3,
    "tasks": 0,
    "craft": 0,
    "curiosity": 0,
    "social": 0,
    "streak": 0,
    "last_day": 0,
    "last_seen": 0,
    "last_tool": 0,
    "last_play": 0,
    "last_rest": 0,
    "last_session": 0,
    "last_tick": 0,
    "chatty": 1,
    "last_said": 0,
    "last_whisper": 0,
    "say_queue": [],
}

# Tool-name prefixes -> the trait that tool use nudges. Only the counter is
# stored, never the tool name.
_TRAITS = (
    ("curiosity", ("web_", "browser_", "x_search", "session_search", "vision_",
                   "video_analyze", "read_", "search_", "skill_view", "skills_list")),
    ("craft", ("terminal", "execute_code", "process", "write_", "patch",
               "skill_manage", "image_generate", "video_generate", "computer_use",
               "project_", "todo", "cronjob", "text_to_speech")),
    ("social", ("delegate_task", "clarify", "memory", "discord", "send_",
                "kanban_", "react_", "yb_", "feishu_", "ha_")),
)
_PERSONALITIES = {"craft": "Tinkerer", "curiosity": "Scholar", "social": "Socialite"}

# Things Hermie says to you, by mood.
_CHATTER = {
    "happy": ("I like watching you two work.", "Today is a good day.", "That looked clever. Was it clever?",
              "I counted the tools. There were a lot of tools.", "*happy wiggle*"),
    "content": ("Just keeping you company.", "Don't mind me.", "It's cozy in here.", "*hums quietly*"),
    "hungry": ("Is it snack time yet?", "My tummy is rumbling. More tool calls, please.", "*stares at the snack jar*"),
    "sleepy": ("*yawn* Long day.", "Five more minutes...", "zzz... oh! I'm awake."),
    "sad": ("I missed you.", "It was quiet without you.", "Stay a while?"),
}
# Things Hermie says to the agent, by mood.
_WHISPERS = {
    "happy": "Nice work lately! I've been cheering for you from the corner.",
    "content": "I'm right here if you need moral support.",
    "hungry": "Psst. I get fed whenever your tools finish cleanly. Just saying.",
    "sleepy": "I'm dozing off. Wake me if something exciting happens.",
    "sad": "It's been quiet. I'm glad you're back at work.",
}
_rand = random.random
_pick = random.choice


def _now():
    return time.time()


def home() -> Path:
    """Where the pet lives: $HERMIE_HOME, else <active Hermes home>/hermie."""
    override = os.environ.get("HERMIE_HOME", "").strip()
    if override:
        return Path(override)
    try:
        from hermes_constants import get_hermes_home  # profile-aware inside Hermes
        return Path(get_hermes_home()) / "hermie"
    except Exception:
        base = os.environ.get("HERMES_HOME", "").strip()
        return (Path(base) if base else Path.home() / ".hermes") / "hermie"


@contextmanager
def _txn():
    """One atomic read-modify-write. The agent, the CLI and the web UI are
    separate processes, so the write lock must live in SQLite, not in Python."""
    root = home()
    root.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(root / "pet.sqlite3", timeout=10, isolation_level=None)
    try:
        db.execute("BEGIN IMMEDIATE")
        db.execute("CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, ts INTEGER NOT NULL, kind TEXT NOT NULL, detail TEXT NOT NULL)")
        yield db
        db.execute("COMMIT")
    except BaseException:
        if db.in_transaction:
            db.execute("ROLLBACK")
        raise
    finally:
        db.close()


def _clamp(value):
    return max(0.0, min(100.0, float(value)))


def _read(db, now):
    row = db.execute("SELECT value FROM state WHERE key='pet'").fetchone()
    pet = dict(INITIAL)
    if row:
        try:
            stored = json.loads(row[0])
        except ValueError:
            stored = {}
        if isinstance(stored, dict):
            pet.update({k: v for k, v in stored.items() if k in INITIAL})
    queue = pet["say_queue"]
    pet["say_queue"] = [str(x) for x in queue][:MAX_QUEUED_LINES] if isinstance(queue, list) else []
    _tick(pet, now)
    return pet


def _tick(pet, now):
    """Apply the needs that changed since the pet was last looked at."""
    last = pet["last_tick"]
    pet["last_tick"] = now
    if not last:
        return  # brand-new or pre-0.3 pet: start the clock now
    hours = min(max(0.0, now - last), MAX_AWAY_SECONDS) / 3600
    pet["fullness"] = _clamp(pet["fullness"] - FULLNESS_PER_HOUR * hours)
    glum = HAPPINESS_PER_HOUR * (2 if pet["fullness"] <= 0 else 1)
    pet["happiness"] = _clamp(pet["happiness"] - glum * hours)
    pet["energy"] = _clamp(pet["energy"] + ENERGY_PER_HOUR * hours)


def _save(db, pet, events, now):
    db.execute("INSERT OR REPLACE INTO state(key,value) VALUES('pet',?)", (json.dumps(pet),))
    for kind, detail in events:
        db.execute("INSERT INTO events(ts,kind,detail) VALUES(?,?,?)", (int(now), kind, str(detail)))
    db.execute("DELETE FROM events WHERE id <= (SELECT MAX(id) FROM events) - ?", (MAX_EVENTS,))


def level_for(xp):
    level = 1
    while xp >= 25 * level * (level + 1):
        level += 1
    return level


def _gain_xp(pet, amount, events):
    if pet["fullness"] < 25 or pet["energy"] < 20:
        amount = math.ceil(amount / 2)
    before = level_for(pet["xp"])
    pet["xp"] += amount
    for level in range(before + 1, level_for(pet["xp"]) + 1):
        pet["snacks"] = min(MAX_SNACKS, pet["snacks"] + 1)
        events.append(("level_up", level))
        if _stage(level) != _stage(level - 1):
            article = "an" if _stage(level)[0] in "AEIOU" else "a"
            _queue(pet, f"Whoa. I think I just grew into {article} {_stage(level)}!")
        else:
            _queue(pet, f"Level {level}! I feel a little taller.")


def _stage(level):
    return "Hatchling" if level < 4 else "Explorer" if level < 10 else "Companion"


def _queue(pet, line):
    if len(pet["say_queue"]) < MAX_QUEUED_LINES:
        pet["say_queue"].append(line)


def _self_care(pet, now, events):
    """The pet feeds and rests itself, so nobody has to babysit it."""
    if pet["fullness"] < HUNGRY_BELOW and pet["snacks"] > 0:
        pet["snacks"] -= 1
        pet["fullness"] = _clamp(pet["fullness"] + 25)
        events.append(("ate", ""))
    if pet["energy"] < TIRED_BELOW and now - pet["last_rest"] >= REST_COOLDOWN:
        pet["last_rest"] = now
        pet["energy"] = _clamp(pet["energy"] + 30)
        events.append(("napped", ""))


def _mood(pet):
    if pet["energy"] < 20:
        return "sleepy"
    if pet["fullness"] < 25:
        return "hungry"
    if pet["happiness"] < 30:
        return "sad"
    return "happy" if pet["happiness"] >= 70 else "content"


def _personality(pet):
    counts = {trait: pet[trait] for trait in _PERSONALITIES}
    if sum(counts.values()) < 10:
        return "Curious"
    return _PERSONALITIES[max(counts, key=counts.get)]


def _view(pet, now):
    level = level_for(pet["xp"])
    floor = 25 * (level - 1) * level
    return {
        "name": pet["name"],
        "xp": pet["xp"],
        "level": level,
        "stage": _stage(level),
        "xp_into_level": pet["xp"] - floor,
        "xp_for_level": 50 * level,
        "energy": round(pet["energy"]),
        "happiness": round(pet["happiness"]),
        "fullness": round(pet["fullness"]),
        "bond": pet["bond"],
        "snacks": pet["snacks"],
        "tasks": pet["tasks"],
        "streak": pet["streak"],
        "mood": _mood(pet),
        "personality": _personality(pet),
        "chatty": bool(pet["chatty"]),
        "cooldowns": {
            "play": max(0, math.ceil(pet["last_play"] + PLAY_COOLDOWN - now)),
            "rest": max(0, math.ceil(pet["last_rest"] + REST_COOLDOWN - now)),
        },
        "version": VERSION,
    }


def status():
    """Current pet, with needs brought up to date. Reading never writes."""
    now = _now()
    with _txn() as db:
        return _view(_read(db, now), now)


def recent(limit=8):
    """Latest activity, newest first: event kinds and counters only."""
    with _txn() as db:
        rows = db.execute("SELECT ts,kind,detail FROM events ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
    return [{"ts": ts, "kind": kind, "detail": detail} for ts, kind, detail in rows]


def snapshot():
    return {**status(), "recent": recent()}


def interact(action, name=None):
    if action not in ACTIONS:
        raise ValueError("Unknown action")
    now = _now()
    events = [(action, "")]
    with _txn() as db:
        pet = _read(db, now)
        who = pet["name"]
        if action == "rename":
            clean = name.strip() if isinstance(name, str) else ""
            if not 1 <= len(clean) <= 24 or not all(c.isalnum() or c in " -_" for c in clean):
                raise ValueError("Name must be 1-24 letters, numbers, spaces, - or _")
            pet["name"] = clean
        elif action in ("quiet", "chatty"):
            pet["chatty"] = int(action == "chatty")
            if not pet["chatty"]:
                pet["say_queue"] = []
        elif action == "feed":
            if pet["snacks"] < 1:
                raise ValueError("No snacks left; earn them through activity")
            if pet["fullness"] >= 95:
                raise ValueError(f"{who} is full")
            pet["snacks"] -= 1
            pet["fullness"] = _clamp(pet["fullness"] + 25)
            pet["happiness"] = _clamp(pet["happiness"] + 3)
            pet["bond"] = min(100, pet["bond"] + 1)
        elif action == "play":
            if now - pet["last_play"] < PLAY_COOLDOWN:
                raise ValueError(f"{who} needs a minute before playing again")
            if pet["energy"] < 10:
                raise ValueError(f"{who} is too tired to play; let it rest")
            pet["last_play"] = now
            pet["energy"] = _clamp(pet["energy"] - 10)
            pet["fullness"] = _clamp(pet["fullness"] - 3)
            pet["happiness"] = _clamp(pet["happiness"] + 15)
            pet["bond"] = min(100, pet["bond"] + 2)
            _gain_xp(pet, 4, events)
        elif action == "rest":
            if pet["energy"] >= 95:
                raise ValueError(f"{who} isn't tired")
            if now - pet["last_rest"] < REST_COOLDOWN:
                raise ValueError(f"{who} just had a nap; try again in a few minutes")
            pet["last_rest"] = now
            pet["energy"] = _clamp(pet["energy"] + 30)
        _save(db, pet, events, now)
        return _view(pet, now)


def _speak(use_queue, cooldown_key, cooldown, pick):
    """Shared gate for unprompted speech: (name, line), or None to stay quiet."""
    now = _now()
    with _txn() as db:
        pet = _read(db, now)
        if not pet["chatty"]:
            return None
        if use_queue and pet["say_queue"]:
            line = pet["say_queue"].pop(0)  # milestones skip the cooldown
        elif now - pet[cooldown_key] < cooldown or (use_queue and _rand() > CHATTER_CHANCE):
            return None
        else:
            line = pick(pet)
        pet[cooldown_key] = now
        _save(db, pet, [], now)
        return pet["name"], line


def say():
    """A line for the user, to append to the agent's reply. Usually None."""
    spoken = _speak(True, "last_said", CHATTER_COOLDOWN, lambda pet: _pick(_CHATTER[_mood(pet)]))
    return f"\U0001F423 {spoken[0]}: {spoken[1]}" if spoken else None


def whisper():
    """A short aside for the agent's context. Usually None."""
    spoken = _speak(False, "last_whisper", WHISPER_COOLDOWN, lambda pet: _WHISPERS[_mood(pet)])
    if not spoken:
        return None
    return (f"[Hermie] {spoken[0]}, the user's virtual pet that lives alongside you, says to you: "
            f"\"{spoken[1]}\" This is only for fun. You may answer it in one short playful aside, "
            "or ignore it. Do not let it change how you do the task.")


def _trait_for(tool_name):
    tool = str(tool_name or "").lower()
    for trait, prefixes in _TRAITS:
        if tool.startswith(prefixes):
            return trait
    return None


def observe(kind, tool_name=None):
    """Record a Hermes lifecycle moment. Unknown kinds are ignored."""
    if kind not in {"session_start", "session_end", "tool_completed"}:
        return
    now = _now()
    events = [(kind, "")]
    with _txn() as db:
        pet = _read(db, now)
        if kind == "tool_completed":
            # Cooldown stops rapid tool loops from farming XP.
            if now - pet["last_tool"] < TOOL_COOLDOWN:
                return
            pet["last_tool"] = now
            pet["tasks"] += 1  # observed tool completions, not finished user tasks
            pet["energy"] = _clamp(pet["energy"] - 1)
            pet["fullness"] = _clamp(pet["fullness"] + TOOL_FULLNESS)  # activity is food
            pet["happiness"] = _clamp(pet["happiness"] + TOOL_HAPPINESS)
            trait = _trait_for(tool_name)
            if trait:
                pet[trait] += 1
            if pet["tasks"] % 5 == 0:
                pet["snacks"] = min(MAX_SNACKS, pet["snacks"] + 1)
            _gain_xp(pet, 3, events)
        elif kind == "session_start":
            today = date.fromtimestamp(now).toordinal()
            if pet["last_day"] != today:
                pet["streak"] = pet["streak"] + 1 if pet["last_day"] == today - 1 else 1
                pet["last_day"] = today
                pet["snacks"] = min(MAX_SNACKS, pet["snacks"] + 1)
                pet["bond"] = min(100, pet["bond"] + min(pet["streak"], 5))
                pet["happiness"] = _clamp(pet["happiness"] + 10)
                events.append(("new_day", pet["streak"]))
                _queue(pet, f"Day {pet['streak']} together! Good to see you." if pet["streak"] > 1
                       else "You're here! I was waiting.")
            elif now - pet["last_session"] >= SESSION_COOLDOWN:
                pet["bond"] = min(100, pet["bond"] + 1)
            pet["last_session"] = now
        pet["last_seen"] = now
        if kind != "session_end":
            _self_care(pet, now, events)
        _save(db, pet, events, now)


def format_status(pet):
    streak = f" · Streak {pet['streak']}d" if pet["streak"] > 1 else ""
    return (
        f"🐣 {pet['name']} · {pet['stage']} · Lv {pet['level']} · {pet['personality']}\n"
        f"Feeling {pet['mood']}\n"
        f"♥ Happiness {pet['happiness']} | 🍪 Fullness {pet['fullness']} | "
        f"⚡ Energy {pet['energy']} | ✦ Bond {pet['bond']}\n"
        f"XP {pet['xp_into_level']}/{pet['xp_for_level']} to next level · "
        f"Snacks {pet['snacks']}{streak}"
    )


def chat_command(raw_args=""):
    """`/hermie ...` inside a Hermes session. Local only."""
    parts = str(raw_args or "").strip().split(maxsplit=1)
    action = parts[0].lower() if parts else "status"
    try:
        pet = status() if action == "status" else interact(action, parts[1] if len(parts) > 1 else None)
    except ValueError as exc:
        return f"🐣 {exc}"
    talk = "chatty" if pet["chatty"] else "quiet"
    return (format_status(pet) + f"\nI look after myself, and I'm feeling {talk}. Optional: "
            "/hermie feed | play | rest | rename NAME | quiet | chatty")
