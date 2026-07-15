# VACSKILLS — One Skill. Any Agent. Zero Amnesia.

**v1.2.1** · [Changelog](CHANGELOG.md) · plain markdown · zero dependencies · MIT

Your AI agent died mid-work? Limit hit? Listen up: open ANOTHER agent, say
`VACSKILL SET`, and it continues EXACTLY where the dead one stopped. No
re-explaining your project like it's a first date. Ever.

## How it works (like you're five)

Robots are hired hands — they come, they go, they run out of juice.
The **notebook** stays. Every robot reads the notebook before work and
writes in it while working. Notebook = team brain. Robot = replaceable.

```
vacskills/                    ← this repo, clone anywhere
  VAC/SKILL.md                the rules every robot obeys
  VAC/UI.md                   the look (Win95 dark gold, sharp pixels)
  inject.ps1 / inject.sh      one-shot installer

your-project/.vac/            ← the notebook (robots make it themselves)
  STATE.md                    where work stands + what to do next
  BOARD.md                    job tickets: TODO / DOING / DONE
  LOG.md                      diary: every test, every decision, one line
```

## Install (three commands, no crying)

```
git clone https://github.com/vacterro/vacskills
cd vacskills
powershell -ExecutionPolicy Bypass -File .\inject.ps1     # Windows
bash inject.sh                                            # macOS / Linux
```

Injector sniffs out every agent on your machine — Claude Code, OpenCode,
Codex, Gemini/Antigravity, Aider — and wires VAC into each as default.
Re-run any time (after `git pull` too); it skips what's already done.
That's it. Damn near idiot-proof.

## How to use

| You say | Robot does |
|---|---|
| `vac build me X` | makes notebook, plans tickets, builds, verifies each |
| `vac` / `vac set` / `VACSKILL SET` | continues whatever notebook says; nothing there → hunts bugs itself |
| `vac fix <thing>` | detective mode: reproduce → root cause → regression test |
| `vac status` | reads notebook aloud, touches nothing |
| `vac stop` | writes goodbye note properly |
| `vac ship` | final inspection → green → your GitHub, versioned + changelog |

**The daily dance:**

1. `vac build me a parser` — robot plans tickets, grinds them one by one.
   Every ticket gets VERIFIED — run, tested, proven. "Probably works" is
   not in the vocabulary.
2. Robot's battery dies mid-ticket? Relax. It wrote checkpoints the whole
   time — dying robots don't get goodbye speeches, so nothing waits for one.
3. Open any other agent: `VACSKILL SET` → "Resume T-004. Next: …" →
   work continues like nothing happened.
4. All green → `vac ship` → beautiful README, tiny version bump
   (`3.1.0 → 3.1.0a` micro, `3.2.1` little, `3.2.0` feature), one-line
   changelog, push to YOUR GitHub. Red never ships. Never.

**Free extras, no coupon needed:**
- **Hunt mode** — bare `vac` on a finished board: robot finds failing
  tests, silent errors, orphan files, half-built features (save exists,
  load missing — classic). Clean repo → says clean, no fake busywork.
- **Self-cleaning** — scratch junk lives in `.vac/tmp/`, deleted at stop.
  No litter in your repo, no `.env` leaked to GitHub. Guards built in.
- **UI law** — any interface comes out Win95 dark golden: Verdana, no
  antialiasing, sharp bevels, zero animations. [VAC/UI.md](VAC/UI.md) —
  non-negotiable, gorgeous.
- **Two voices** — chat answers: short, funny, no fluff. LOG diary: wise
  angry grandpa with human dates (`15.07.26 14:32`, not ISO soup) and one
  closing haiku per session. Facts stay exact in both — comedy never eats
  evidence.

## Why it doesn't fall apart

- Checkpoints after EVERY ticket — worst crash loses one ticket, `git
  status` shows even that.
- Every debug loop has a hard cap — 3 dead guesses = BLOCKED with facts,
  next ticket. No robot spinning in circles burning your money.
- Publish is opt-in — your projects never get pushed to GitHub uninvited.
- Two agents, same project? Takeover guard asks before grabbing the wheel.

## House rules (for editing this system)

One skill — add a section, not a file. If the model already knows it,
don't write it. Every rule must be checkable. Short beats clever.

MIT. Take it, use it, ship your own stuff with it.
