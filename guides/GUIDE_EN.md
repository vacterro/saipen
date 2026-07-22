<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# SAIPEN Guide

Listen here, rookie. The problem is simple: your AI agents have the memory of a goldfish. Yesterday you spent half a day explaining your architecture, and today you open a fresh chat and it starts building everything from scratch while asking stupid questions.

**SAIPEN** is just a damn notebook. A hard, fireproof notebook that sits in the `.saipen/` folder right inside your project.

The agent wakes up, opens this notebook (`STATE.md` and `BOARD.md`), sees exactly which line of code it left off at yesterday, and gets back to work. No whining, no repeating yourself.

## How to fire it up (for the specially gifted)

**Step 1. Beat the rules into the agent's skull (Once per machine)**
You have agents living on your machine (Claude, Gemini, Aider, whatever). Download SAIPEN and run the script. It writes a global rule into their brains telling them to always read the notebook.
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**Step 2. Start it in your project**
Open your terminal or editor in your project folder, call the agent, and tell it straight to its face:
> `saipen set` 

It will grumble, create an `.saipen/` folder, and start writing a list of tasks (tickets). Bam, the patient is on the hook.

**Step 3. Make it work**
- You just type `saipen` — the agent shuts up, reads what it planned, picks the top task, and does it.
- The next day, you open a completely blank chat, type `saipen` again — it picks up the old notes from the folder and resumes exactly where it stopped.

And if you need it to permanently remember that you only use Tabs and not Spaces — toss a text file into `.saipen/KNOWLEDGE/`. It will read it like the Ten Commandments before every single task.

The agent also has a `.saipen/kitchen/` folder. This is its workbench. It drops all its half-finished files, scratchpads, and intermediate drafts here so it doesn't litter your main project. If an agent dies mid-task, the next one picks up right from the kitchen.

**Step 4. Evolution (for lazy asses)**
Board empty? Bored? Just type `saipen` again.
Since there's no active work, the agent won't whine 'how can I help?'. It automatically jumps to **HUNT**, seeks bugs. No bugs? Hits **ADD** and builds a new feature by strict rules: zero hardcoding, bulletproof persistence, user controls everything. You just sit, smoke, watch the app grow muscles itself.

**Step 5. Spring Cleaning**
Type `saipen clean`. The agent will roll up its sleeves, prune your old finished tickets, delete orphaned files, fix broken paths, and make sure the repo is crisp and fresh.

**Step 6. Don't panic about the mess**
You'll open the project one day and see a pile of uncommitted changes staring back at you. That's not a disaster, that's Tuesday -- the agent only actually commits at `ship`, so half-finished work sitting there is completely normal. It figures out whose mess it is before touching anything: its own unfinished ticket, it keeps going; somebody else's edits (yours, some other tool's), it doesn't lay a finger on them. No surprise commits, no surprise reverts.

**Step 7. Make it remember house rules forever**
Beyond the "tabs not spaces" trick -- if you want it to remember an actual architectural decision (why Postgres over Mongo, why that one module is cursed), drop it in `.saipen/KNOWLEDGE/` as either one running `decisions.md` or numbered files like `ADR-001.md`. Either way it gets read like scripture before planning starts.

**When it can't do something, it says so**
No git on this machine? It won't fake a push and lie to you. No shell? It'll hand you the exact command to run yourself and wait for the verdict. It checks what it's actually allowed to touch before it touches anything -- that's the whole point of a `WAIT: <question>` message. Answer it, it moves.

**Paranoid? Lock the door**
```bash
python <saipen-clone>/tools/install_hook.py
```
Installs a pre-commit hook. Broken board, malformed log line -- caught before the commit, not three sessions later when you're trying to figure out who broke what. Done with it? `python <saipen-clone>/tools/uninstall_hook.py` takes it back off (and restores any hook it replaced).

**Experimental: spawn yourself some read-only researchers**
`saipen sub spawn saihunt` -- one command, bootstraps `.saipen/extensions/subs/` itself from the SAIPEN home if this project's never seen it, no manual copying. Gets you an isolated, read-only agent that pokes through your project and hands findings back through its own `OUTBOX.md` -- never touches your actual code. Two come built in: `saiwiki` (drafts your docs) and `saihunt` (hunts bugs). Brand new, zero battle scars yet -- kick the tires, don't bet the farm on it.

Any questions? No? Then get back to work.

## All Commands & Use Scenarios (Cheat Sheet)

Think of the agent as a smart dog. These are the commands you use to tell it what to do.

| Command | What it does (ELI5) | When to use it (Scenario) |
|---|---|---|
| `saipen set` (or `saipen init`) | **The On-Switch.** Creates the memory folder (`.saipen/`) and starts the first planning session. | *Scenario:* You just opened a completely new project folder and want the agent to start managing it. |
| `saipen continue` | **The Workhorse.** Tells the agent to shut up, read its notes, pick the top task from the board, and do it. | *Scenario:* You come back from lunch, open a blank chat, and want the agent to resume coding exactly where it left off. |
| `saipen stop` | **The Brakes.** Forces the agent to stop what it's doing, save its progress, and wait for you. | *Scenario:* The agent is going down a rabbit hole or you need to urgently push code to production. |
| `saipen status` | **The Status Report.** The agent looks at the board and tells you what's done and what's next, without touching the code. | *Scenario:* You haven't checked the project in a week and just want to know what the current plan is. |
| `saipen goal <text>` | **The Boss Move.** Shoves the current plan in the drawer -- doesn't shred it, old tickets just wait their turn -- and drives the new objective home solo: plans it, builds it, tests it, and ships it, no "should I continue?" hand-holding. Shipping isn't the finish line either -- it keeps going into autonomous bug-hunting and feature-completion until the product is genuinely mature, hits a wall, or trips its own safety cap (3 waves or 20 tickets, whichever comes first). | *Scenario:* The boss just called and said "Pivot everything, we're building a crypto app now." You type `saipen goal build crypto app` and go get coffee. |
| `saipen clean` | **The Janitor.** The agent scrubs the repository, deletes orphaned files, fixes bad links, and prunes old done tasks. | *Scenario:* Your repo is full of `.tmp` files, old `TODO`s, and dead code, and you want a fresh start before a major release. |
| `saipen translate` | **The Interpreter.** Builds out a full translation bundle for the software (32 languages) in a sealed-off folder, never touching your actual source code while it works. | *Scenario:* You're shipping to a global audience and need every string translated without risking a stray edit to the real app. |
| `saipen ship` | **The Launch Button.** Explicitly triggers a release -- version bump, changelog, git tag, push -- even outside the normal build-and-verify flow. | *Scenario:* Everything's already built and verified, you just want to cut the release right now. |
| `saipen validate` | **The Inspector.** Runs the conformance checker against `.saipen/` and fixes whatever structural corruption it finds before you keep working. | *Scenario:* Something feels off about the board or log and you want the agent to sanity-check its own memory before trusting it. |
| `saipen sub spawn <name>` | **The Spy.** Experimental -- spawns an isolated, read-only research agent (`.saipen/extensions/subs/`) that pokes through your project and hands back findings, never edits anything itself. | *Scenario:* You want a second opinion hunting bugs or drafting docs, without letting anything near your actual code. |
| `saipen` | **The Universal "Go" Button.** Acts exactly like `saipen continue` to resume work if there are tickets. If the board is totally empty, it switches to Auto-Pilot (HUNT/ADD) to find bugs or build new features. | *Scenario:* You are lazy and just want the agent to do whatever needs to be done next, whether that's finishing a task or finding new ones. |


<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>
