// Hermie's home: one view shared by the standalone page and the Hermes
// dashboard tab. No dependencies. Usage:
//   const unmount = HermieView.mount(element, { load, act });
// `load()` and `act(action, name)` return a promise of the pet snapshot.
(function () {
  "use strict";

  // ---- Pixel art -----------------------------------------------------
  // 16x16 grids. "." is empty; other letters index PALETTE. Eyes and mouth
  // are drawn on top so one sprite can blink, smile, sulk and sleep.
  const SPRITES = {
    Hatchling: {
      accent: "#8fd694",
      eyes: [[4, 7], [9, 7]], mouth: [6, 9], blush: [[3, 9], [12, 9]],
      rows: [
        "................",
        "........a.......",
        ".......a........",
        ".....oooooo.....",
        "...oobbbbbboo...",
        "..obbhhbbbbbbo..",
        "..obhbbbbbbbbo..",
        "..obbbbbbbbbbo..",
        "..obbbbbbbbbbo..",
        "..obbbbbbbbbbo..",
        ".eobbbbbbbbbboe.",
        ".eeesbbbbbbseee.",
        ".oeeeeesseeeeeo.",
        "..oeeeeeeeeeeo..",
        "...oooooooooo...",
        "................",
      ],
    },
    Explorer: {
      accent: "#f2788f",
      eyes: [[4, 6], [9, 6]], mouth: [6, 8], blush: [[2, 8], [13, 8]],
      rows: [
        "................",
        "..oo........oo..",
        ".obbo......obbo.",
        ".obpboooooobpbo.",
        ".obbbbbbbbbbbbo.",
        ".obhhbbbbbbbbbo.",
        ".obhbbbbbbbbbbo.",
        ".obbbbbbbbbbbbo.",
        ".obbbbbbbbbbbbo.",
        ".obbbbbbbbbbbbo.",
        "..oaaaaaaaaaao..",
        "..obbbaabbbbbo..",
        "..obbbbabbbbbo..",
        "..osbbbbbbbbso..",
        "..oooooooooooo..",
        "...oo......oo...",
      ],
    },
    Companion: {
      accent: "#ffd866",
      eyes: [[4, 7], [9, 7]], mouth: [6, 9], blush: [[3, 9], [12, 9]],
      rows: [
        ".......aa.......",
        "......aaaa......",
        ".......aa.......",
        "..oo.oooooo.oo..",
        ".obboobbbboobbo.",
        ".obbbbbbbbbbbbo.",
        "..obbhbbbbbbbo..",
        "..obbbbbbbbbbo..",
        "wwobbbbbbbbbboww",
        ".wobbbbbbbbbbow.",
        "..obbbbbbbbbbo..",
        "..obbbbaabbbbo..",
        "..osbbbaabbbso..",
        "..oooooooooooo..",
        "...oo......oo...",
        "................",
      ],
    },
  };
  const PALETTE = { o: "#4a2c4f", b: "#ffbb7c", s: "#e8956a", h: "#ffe2bd", e: "#fff4e3", w: "#f6efff", p: "#ff9fb0" };
  const INK = "#35243e";
  const EYES = {
    open: [[0, 0, INK], [1, 0, INK], [0, 1, INK], [1, 1, INK], [0, 0, "#ffffff"]],
    closed: [[0, 1, INK], [1, 1, INK], [2, 1, INK]],
    happy: [[0, 1, INK], [1, 0, INK], [2, 1, INK]],
  };
  const MOUTHS = {
    neutral: [[1, 0, INK], [2, 0, INK]],
    happy: [[0, 0, INK], [1, 1, INK], [2, 1, INK], [3, 0, INK]],
    sad: [[0, 1, INK], [1, 0, INK], [2, 0, INK], [3, 1, INK]],
    sleep: [[1, 0, INK], [2, 0, INK], [1, 1, INK], [2, 1, INK]],
  };
  const FACES = {
    neutral: ["open", "neutral"], happy: ["happy", "happy"], sad: ["open", "sad"],
    sleep: ["closed", "sleep"], blink: ["closed", "neutral"],
  };

  // -> [x, y, width, color] runs for one sprite and expression.
  function spritePixels(stage, face) {
    const sprite = SPRITES[stage] || SPRITES.Hatchling;
    const out = [];
    sprite.rows.forEach((row, y) => {
      let x = 0;
      while (x < row.length) {
        const ch = row[x];
        let end = x + 1;
        while (end < row.length && row[end] === ch) end++;
        if (ch !== ".") out.push([x, y, end - x, ch === "a" ? sprite.accent : PALETTE[ch]]);
        x = end;
      }
    });
    const [eyes, mouth] = FACES[face] || FACES.neutral;
    for (const [ex, ey] of sprite.eyes) for (const [dx, dy, c] of EYES[eyes]) out.push([ex + dx, ey + dy, 1, c]);
    for (const [dx, dy, c] of MOUTHS[mouth]) out.push([sprite.mouth[0] + dx, sprite.mouth[1] + dy, 1, c]);
    if (face !== "sad") for (const [bx, by] of sprite.blush) out.push([bx, by, 1, PALETTE.p]);
    return out;
  }

  const SVG_NS = "http://www.w3.org/2000/svg";
  function drawSprite(svg, stage, face) {
    svg.replaceChildren();
    for (const [x, y, w, color] of spritePixels(stage, face)) {
      const rect = document.createElementNS(SVG_NS, "rect");
      rect.setAttribute("x", x); rect.setAttribute("y", y);
      rect.setAttribute("width", w); rect.setAttribute("height", 1);
      rect.setAttribute("fill", color);
      svg.append(rect);
    }
  }

  // ---- Small helpers -------------------------------------------------
  function h(tag, props, ...children) {
    const el = document.createElement(tag);
    for (const [key, value] of Object.entries(props || {})) {
      if (key === "class") el.className = value;
      else if (key === "text") el.textContent = value;
      else el.setAttribute(key, value);
    }
    el.append(...children);
    return el;
  }
  const escapeXml = s => String(s).replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;" }[ch]));

  const EVENT_LABELS = {
    feed: "Had a snack", play: "Played together", rest: "Took a nap", rename: "Got a new name",
    ate: "Helped itself to a snack", napped: "Dozed off for a nap", quiet: "Went quiet", chatty: "Got chatty again",
    tool_completed: "Watched a tool finish", session_start: "Session started", session_end: "Session ended",
    level_up: "Reached level {}", new_day: "Day {} of the streak",
  };
  const BUBBLES = {
    sleepy: ["So sleepy... zzz"],
    hungry: ["My tummy is rumbling..."],
    sad: ["I missed you."],
    content: ["Nice and cozy.", "What are we making?"],
    happy: ["Nice to see you! ♡", "Let's make something!", "What a cozy day ✦", "I like it here!"],
  };
  function ago(ts) {
    const s = Math.max(0, Date.now() / 1000 - ts);
    if (s < 60) return "just now";
    if (s < 3600) return Math.floor(s / 60) + "m ago";
    if (s < 86400) return Math.floor(s / 3600) + "h ago";
    return Math.floor(s / 86400) + "d ago";
  }

  // ---- The view ------------------------------------------------------
  function mount(root, api) {
    let pet = null;
    let loadedAt = 0;
    let celebrating = false;
    let blinking = false;
    const timers = [];
    const every = (fn, ms) => timers.push(setInterval(fn, ms));

    const sprite = document.createElementNS(SVG_NS, "svg");
    sprite.setAttribute("viewBox", "0 0 16 16");
    sprite.setAttribute("shape-rendering", "crispEdges");
    sprite.setAttribute("class", "hm-sprite");
    const petButton = h("button", { class: "hm-pet", type: "button", "aria-label": "Boop your companion" });
    petButton.append(sprite);
    const bubble = h("div", { class: "hm-bubble", text: "Hello, friend! ♡" });
    const zzz = h("div", { class: "hm-zzz", "aria-hidden": "true", text: "z z z" });
    const plant = h("button", { class: "hm-plant", type: "button", "aria-label": "Look at the house plant", text: "🌿" });
    const scene = h("div", { class: "hm-scene" },
      h("div", { class: "hm-window" }, h("div", { class: "hm-moon" })),
      h("div", { class: "hm-shelf", "aria-hidden": "true", text: "📚 🧸" }),
      h("div", { class: "hm-floor" }), h("div", { class: "hm-rug" }),
      plant, zzz, bubble, h("div", { class: "hm-shadow" }), petButton);

    const nameEl = h("h2", { class: "hm-name", text: "Hermie" });
    const stageEl = h("span", { class: "hm-pill", text: "HATCHLING" });
    const levelEl = h("span", { class: "hm-level", text: "LVL 01" });
    const subline = h("p", { class: "hm-subline", text: "Loading..." });
    function meter(label, kind) {
      const num = h("strong", { text: "0" });
      const fill = h("div", { class: "hm-fill hm-fill-" + kind });
      const el = h("div", { class: "hm-meter" },
        h("div", { class: "hm-between" }, h("span", { text: label }), num),
        h("div", { class: "hm-track" }, fill));
      return { el, set(value, text) { fill.style.width = Math.max(0, Math.min(100, value)) + "%"; num.textContent = text === undefined ? value : text; } };
    }
    const xp = meter("EXPERIENCE", "xp");
    const meters = {
      happiness: meter("♥ HAPPINESS", "happy"), fullness: meter("🍪 FULLNESS", "full"),
      energy: meter("⚡ ENERGY", "energy"), bond: meter("✦ BOND", "bond"),
    };
    const snacks = h("strong", { text: "0" }), tasks = h("strong", { text: "0" }), streak = h("strong", { text: "0" });
    const buttons = {};
    const BUTTON_TEXT = { feed: "🍪 Feed", play: "🎮 Play", rest: "🌙 Rest" };
    for (const action of Object.keys(BUTTON_TEXT)) {
      buttons[action] = h("button", { type: "button", text: BUTTON_TEXT[action] });
      buttons[action].addEventListener("click", () => act(action));
    }
    const starScore = h("span", { text: "0 / 5" });
    const starStart = h("button", { type: "button", text: "Start mini-game" });
    const starField = h("div", { class: "hm-starfield", "aria-label": "Star catch game" });
    const renameInput = h("input", { maxlength: "24", "aria-label": "New name", placeholder: "Give your companion a new name" });
    const renameButton = h("button", { type: "button", text: "Rename" });
    const exportButton = h("button", { class: "hm-export", type: "button", text: "✦ Export companion card" });
    const feed = h("ul", { class: "hm-feed" });
    const message = h("p", { class: "hm-message", role: "status", text: "Your companion looks after itself. These are just for fun." });

    const panel = h("div", { class: "hm-panel" },
      h("div", { class: "hm-between" }, h("span", { class: "hm-eyebrow", text: "YOUR COMPANION" }), stageEl),
      h("div", { class: "hm-identity" }, nameEl, levelEl),
      subline, xp.el,
      h("div", { class: "hm-stats" }, ...Object.values(meters).map(m => m.el)),
      h("div", { class: "hm-inventory" },
        h("span", { text: "SNACKS " }, snacks), h("span", { text: "TOOL MOMENTS " }, tasks), h("span", { text: "STREAK " }, streak)),
      h("div", { class: "hm-actions" }, ...Object.values(buttons)),
      message,
      h("div", { class: "hm-box" },
        h("div", { class: "hm-between" }, h("span", { text: "✦ STAR CATCH" }), starScore),
        h("p", { text: "Catch five stars to make your companion dance. Just for fun: no XP." }),
        starStart, starField),
      h("div", { class: "hm-rename" }, renameInput, renameButton),
      exportButton,
      h("div", { class: "hm-box" }, h("span", { class: "hm-eyebrow", text: "RECENT ACTIVITY" }), feed));

    root.classList.add("hermie");
    root.replaceChildren(h("div", { class: "hm-grid" }, scene, panel));

    function say(text) { message.textContent = text; }
    function face() {
      if (!pet) return "neutral";
      if (pet.mood === "sleepy") return "sleep";
      if (celebrating) return "happy";
      if (blinking) return "blink";
      return pet.mood === "happy" ? "happy" : pet.mood === "sad" || pet.mood === "hungry" ? "sad" : "neutral";
    }
    function redraw() { drawSprite(sprite, pet ? pet.stage : "Hatchling", face()); }
    function cooldown(action) {
      if (!pet || !pet.cooldowns || !(action in pet.cooldowns)) return 0;
      return Math.max(0, Math.ceil(pet.cooldowns[action] - (Date.now() - loadedAt) / 1000));
    }
    function refreshButtons() {
      for (const action of Object.keys(buttons)) {
        const wait = cooldown(action);
        buttons[action].disabled = !pet || wait > 0;
        buttons[action].textContent = BUTTON_TEXT[action] + (wait ? " (" + (wait >= 60 ? Math.ceil(wait / 60) + "m" : wait + "s") + ")" : "");
      }
    }
    function render(next) {
      pet = next; loadedAt = Date.now();
      nameEl.textContent = pet.name;
      stageEl.textContent = pet.stage.toUpperCase();
      levelEl.textContent = "LVL " + String(pet.level).padStart(2, "0");
      subline.textContent = pet.personality + " companion · feeling " + pet.mood;
      xp.set(100 * pet.xp_into_level / pet.xp_for_level, pet.xp_into_level + " / " + pet.xp_for_level + " XP");
      for (const key of Object.keys(meters)) meters[key].set(pet[key]);
      snacks.textContent = pet.snacks; tasks.textContent = pet.tasks;
      streak.textContent = pet.streak + (pet.streak === 1 ? " day" : " days");
      const lines = BUBBLES[pet.mood] || BUBBLES.content;
      bubble.textContent = lines[Math.floor(pet.xp / 20) % lines.length];
      scene.classList.toggle("hm-asleep", pet.mood === "sleepy");
      feed.replaceChildren(...(pet.recent || []).map(event =>
        h("li", null, h("span", { text: (EVENT_LABELS[event.kind] || event.kind).replace("{}", event.detail) }), h("time", { text: ago(event.ts) }))));
      if (!feed.children.length) feed.append(h("li", { class: "hm-empty", text: "Nothing yet. Use Hermes and check back." }));
      refreshButtons(); redraw();
    }
    function celebrate() {
      celebrating = true; redraw();
      petButton.classList.remove("hm-celebrate"); void petButton.offsetWidth; petButton.classList.add("hm-celebrate");
      setTimeout(() => { celebrating = false; petButton.classList.remove("hm-celebrate"); redraw(); }, 1600);
    }
    const DONE = { feed: "Yum! That hit the spot.", play: "That was fun! ✦", rest: "A little nap. Much better.", rename: "Your companion has a new name!" };
    async function act(action, name) {
      try {
        render(await api.act(action, name));
        say(DONE[action]);
        if (action === "feed" || action === "play") celebrate();
        return true;
      } catch (e) { say(e.message || "Something went wrong."); return false; }
    }
    function refresh(force) {
      if (document.hidden && force !== true) return;  // don't poll in a background tab
      api.load().then(render).catch(e => { if (!pet) say("Unable to load your companion: " + (e.message || e)); });
    }

    renameButton.addEventListener("click", async () => { if (await act("rename", renameInput.value)) renameInput.value = ""; });
    renameInput.addEventListener("keydown", e => { if (e.key === "Enter") renameButton.click(); });
    plant.addEventListener("click", () => { bubble.textContent = "I water this plant! 🌿"; say("The little plant is thriving."); });
    petButton.addEventListener("click", () => { if (pet && pet.mood !== "sleepy") { celebrate(); bubble.textContent = "Boop! ♡"; } });

    exportButton.addEventListener("click", () => {
      if (!pet) return say("Your companion has not loaded yet.");
      const art = spritePixels(pet.stage, pet.mood === "sleepy" ? "sleep" : "happy")
        .map(([x, y, w, c]) => `<rect x="${x}" y="${y}" width="${w}" height="1" fill="${c}"/>`).join("");
      const line = (y, size, fill, text) => `<text x="430" y="${y}" fill="${fill}" font-family="monospace" font-size="${size}">${escapeXml(text)}</text>`;
      const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="900" height="500" viewBox="0 0 900 500">` +
        `<rect width="900" height="500" rx="28" fill="#181325"/><rect x="22" y="22" width="856" height="456" rx="20" fill="#2a203e" stroke="#bd85b6" stroke-width="3"/>` +
        `<circle cx="235" cy="250" r="150" fill="#3a2c52"/><g transform="translate(107 122) scale(16)" shape-rendering="crispEdges">${art}</g>` +
        line(105, 24, "#f9b881", "HERMIE · COMPANION CARD") + line(195, 46, "#fff0df", pet.name) +
        line(247, 25, "#e7b5fa", pet.stage + " · LEVEL " + pet.level) + line(307, 24, "#fff0df", pet.personality) +
        line(362, 21, "#d9c3d9", "XP " + pet.xp + "   BOND " + pet.bond + "   STREAK " + pet.streak) +
        line(430, 17, "#a99bb8", "A LITTLE WORLD FOR HERMES AGENTS") + `</svg>`;
      const url = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
      const link = h("a", { href: url, download: "hermie-companion.svg" });
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      say("Your companion card is ready!");
    });

    let starTimer = null;
    function stopStars() {
      if (starTimer !== null) { clearInterval(starTimer); starTimer = null; }
      starField.replaceChildren(); starStart.disabled = false;
    }
    starStart.addEventListener("click", () => {
      stopStars();
      let score = 0, spawned = 0;
      starScore.textContent = "0 / 5"; starStart.disabled = true;
      say("Catch the stars before they disappear!");
      starTimer = setInterval(() => {
        if (spawned++ >= 12) { stopStars(); say(score >= 5 ? "Five stars! ✦" : "So close. Try again!"); return; }
        const star = h("button", { type: "button", class: "hm-star", "aria-label": "Catch star", text: "✦" });
        star.style.left = (8 + Math.random() * 78) + "%";
        star.style.top = (12 + Math.random() * 60) + "%";
        star.addEventListener("click", () => {
          if (!star.isConnected) return;
          star.remove(); score++;
          starScore.textContent = score + " / 5";
          if (score >= 5) { stopStars(); celebrate(); say("Five stars! Your companion is dancing! ✦"); }
        });
        starField.append(star);
        setTimeout(() => star.remove(), 2200);
      }, 750);
    });

    redraw(); refreshButtons(); refresh(true);
    every(refresh, 15000);
    const onVisible = () => refresh();
    document.addEventListener("visibilitychange", onVisible);
    every(refreshButtons, 1000);
    every(() => { blinking = true; redraw(); setTimeout(() => { blinking = false; redraw(); }, 160); }, 4200);

    return function unmount() {
      timers.forEach(clearInterval); stopStars();
      document.removeEventListener("visibilitychange", onVisible);
      root.replaceChildren(); root.classList.remove("hermie");
    };
  }

  window.HermieView = { mount, spritePixels };
})();
