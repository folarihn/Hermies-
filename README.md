# HERMIE 🐣

**A tiny virtual companion that grows with your Hermes agent.**

Hermie is an early open-source Hermes plugin. It stores a pet locally in SQLite, reacts to supported Hermes lifecycle events, and lets you feed, play with, rest, and rename your pet. This is an **early playable prototype** with a local animated pixel-art room. The art, host integration and gameplay will continue to evolve.

## What works today

- Local persistent pet state, XP, level, energy, happiness, bond and snacks
- Hatchling → Explorer → Companion stages
- Session start/end hooks and conservative tool-completion observation
- A 20-second XP cooldown to prevent farming from rapid tool calls
- CLI actions for feeding, playing, resting and renaming\n- Local browser game with animated CSS pixel pet, mood meters, interactions, a star-catching mini-game, clickable room objects, and SVG companion-card export\n- Hermes chat command: `/hermie status|feed|play|rest|rename NAME` (requires host support)
- No network calls or telemetry in the pet engine

**Important:** XP for tool completion is awarded when Hermes emits `post_tool_call`, unless the result explicitly indicates an error. This is an observed tool operation, not proof of task success. Hermes host versions may represent outcomes differently; integration verification is still required. The `tasks` field counts observed successful tool operations, not completed user tasks.

## Install

Requires Python 3.11+ and a compatible Hermes installation. In a disposable Hermes profile:

```bash
hermes plugins install https://github.com/folarihn/Hermies-.git --enable
hermes plugins list
```

Restart Hermes. Plugin loading and hooks must be checked on your installed Hermes version. This initial code has not yet completed end-to-end host testing.

## Open the pixel-art home\n\nFrom the repository checkout, run:\n\n```bash\npython hermie_web.py\n```\n\nOpen the **private local URL** printed in the terminal. The server binds to `127.0.0.1:8766` and requires a randomly generated token for its API. Keep the link private and do not expose the service through a public reverse proxy. The browser stores the token only in the current tab session.\n\nThe game works without remote assets, external services, or telemetry. You can export a shareable SVG pet card.\n\n## Play locally

Clone the repository, then:

```bash
python hermie_cli.py status
python hermie_cli.py feed
python hermie_cli.py play
python hermie_cli.py rest
python hermie_cli.py rename Pixel
```

State lives in `$HERMIE_HOME/pet.sqlite3` if set, otherwise `$HERMES_HOME/hermie/pet.sqlite3`, otherwise `~/.hermes/hermie/pet.sqlite3`. No external Python dependencies are required.

## Test checklist\n\nRun `python -m unittest discover -s tests -v` and `node --check web/app.js`. Then start `python hermie_web.py` and open the tokenized URL from the terminal. Verify feeding, play cooldown, rest, renaming, pet card export, clicking the plant, and catching five stars. Restart the server and confirm pet progress persists. Test `/hermie status` separately inside Hermes. The browser mini-game is cosmetic and does not award XP, preventing easy reward farming.\n\n## Roadmap

- Verify Hermes lifecycle hook payloads on supported host versions
- Add chat commands and a small browser-based pixel-art home
- Add pet animations, collectibles and evolution artwork
- Add exportable companion cards
- Tests, CI, and a short playable hackathon demo

No private chat text, tool arguments or tool output is stored by this prototype. The pet tracks only aggregate progress and minimal local event types. The plugin does not grant tools permissions or modify the agent's work.
