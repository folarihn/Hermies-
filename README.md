# HERMIE 🐣

**A tiny virtual companion that grows with your Hermes agent.**

Hermie is an early open-source Hermes plugin. It stores a pet locally in SQLite, reacts to supported Hermes lifecycle events, and lets you feed, play with, rest, and rename your pet. This is the **first engine prototype**, not the finished animated game.

## What works today

- Local persistent pet state, XP, level, energy, happiness, bond and snacks
- Hatchling → Explorer → Companion stages
- Session start/end hooks and conservative tool-completion observation
- A 20-second XP cooldown to prevent farming from rapid tool calls
- CLI actions for feeding, playing, resting and renaming
- No network calls or telemetry in the pet engine

**Important:** XP for tool completion is awarded only when the host explicitly supplies a recognized success flag. Hermes host versions may represent tool outcomes differently; integration verification is still required. The `tasks` field counts observed successful tool operations, not completed user tasks.

## Install

Requires Python 3.11+ and a compatible Hermes installation. In a disposable Hermes profile:

```bash
hermes plugins install https://github.com/folarihn/Hermies-.git --enable
hermes plugins list
```

Restart Hermes. Plugin loading and hooks must be checked on your installed Hermes version. This initial code has not yet completed end-to-end host testing.

## Play locally

Clone the repository, then:

```bash
python hermie_cli.py status
python hermie_cli.py feed
python hermie_cli.py play
python hermie_cli.py rest
python hermie_cli.py rename Pixel
```

State lives in `$HERMIE_HOME/pet.sqlite3` if set, otherwise `$HERMES_HOME/hermie/pet.sqlite3`, otherwise `~/.hermes/hermie/pet.sqlite3`. No external Python dependencies are required.

## Roadmap

- Verify Hermes lifecycle hook payloads on supported host versions
- Add chat commands and a small browser-based pixel-art home
- Add pet animations, collectibles and evolution artwork
- Add exportable companion cards
- Tests, CI, and a short playable hackathon demo

No private chat text, tool arguments or tool output is stored by this prototype. The plugin does not grant tools permissions or modify the agent's work.
