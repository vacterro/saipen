# SAIPEN

## The agent forgets. The project remembers.

**SAIPEN — a file-based continuation protocol for AI agents.**

It keeps the project's memory not in the chat, not in some hazy "long-term memory" of a service, and not in the head of a particular model, but right next to the code, in plain Markdown files.

Today Claude works.
Tomorrow GPT.
The day after tomorrow Gemini, Qwen, or some other electronic shaman.

The model changes. The context disappears. The project keeps working.

**Agent dies. Project remembers.**
**Agent kaob. Projekt mäletab.**
**エージェントは消える。プロジェクトは覚える。**
*[Ējento wa kieru. Purojekuto wa oboeru. The agent disappears. The project remembers.]*

---

## The problem

An ordinary coding agent lives like a goldfish with terminal access.

It spends twenty minutes studying the project, understands the architecture, finds the bug, starts fixing it — and hits the limit or gets closed.

A new agent arrives:

> What are we doing?
> Which files matter?
> What has already been checked?
> What must not be touched?
> Continue?

And the human retells the project's story. Then again. Then writes a huge `CLAUDE.md`. Then the file turns into a sacred dump of old decisions, random prohibitions, and phrases the model once misunderstood.

SAIPEN says:

> Stop storing the project in a conversation.
> Put the state next to the project.
> A new agent will read it and continue.

---

# What SAIPEN can do

## 1. Continue work without chat history

The user writes:

```text
saipen continue
```

or in short:

```text
cc
```

A cold agent reads:

```text
STATE.md
BOARD.md
tail of LOG.md
human_note
```

Then it executes the recorded `next_action`.

It does not conduct interviews.
It does not ask you to repeat the architecture.
It does not invent a new plan on top of the old one.
It does not pretend to be "familiar with the context" after reading the first twenty lines.

It continues the work from a concrete point.

---

## 2. Store project memory in plain files

SAIPEN separates memory by purpose.

### `STATE.md`

Answers the question:

> What to do right now?

It holds the current phase, the active ticket, the working mode, the exact next action, and important constraints.

### `BOARD.md`

Answers:

> What work exists?

Tasks are split into:

```text
DOING
TODO
BLOCKED
DONE
```

Every task has a priority, dependencies, verification conditions, and a reason for blocking.

### `LOG.md`

Answers:

> What actually happened and why did we end up here?

Not "we are going to check".
Not "probably fixed".
But a concrete event, command, result, and the link to previous decisions.

### `KNOWLEDGE/`

Answers:

> What is the durable truth of the project?

Architectural decisions, constraints, conventions, and ADRs do not drown in kilometers of a temporary log.

### `kitchen/`

A workbench.

Drafts, intermediate materials, prepared packages, and unfinished work stay there so that a session death does not turn half an hour of labor into ashes and philosophy.

---

## 3. Give the agent one exact next action

The heart of SAIPEN is the field:

```yaml
next_action:
```

The agent should not re-decide every session what to do.

The project already knows the next step:

```text
PHASE SCOUT T-399
RUN validate.py
VERIFY T-501
WAIT: destructive-op
SHIP release
```

One state.
One command.
One reality.

The less the agent improvises in process management, the more brain is left for the actual task. A rare case where bureaucracy does not hinder the work but stops the neural network from running off into the woods with a screwdriver.

---

## 4. Run work through a strict state machine

Work moves through phases:

```text
INIT
→ PLAN
→ SCOUT
→ BUILD
→ VERIFY
→ REVIEW
→ SHIP
→ DONE
```

There are also special phases:

```text
BLOCKED
HUNT
MARKHUNT
ADD
CLEAN
TRANSLATE
PREPARE
VALIDATE
```

Each phase knows:

* what the agent must read;
* what it is allowed to change;
* what counts as completion;
* where to go next;
* when it must stop;
* what evidence to leave behind.

The agent cannot declare a task done right after the first green test. First BUILD, then VERIFY, then REVIEW, then SHIP.

Because "it ran once on my machine" is not an engineering standard. It is a folk belief.

---

## 5. Work with different models and tools

SAIPEN does not belong to one company.

It is built to work with:

* Claude Code;
* OpenAI Codex;
* Gemini;
* OpenCode;
* Aider;
* Antigravity;
* DeepSeek;
* Qwen;
* other agents capable of reading files and running commands.

Platforms have adapters and injectors, but the foundation stays the same:

```text
plain files
plain Git
plain Markdown
```

No proprietary memory.
No mandatory database.
No eternal background daemon that will update tomorrow and decide your project must now live in a cloud pot.

---

## 6. Execute a long goal on its own

The command:

```text
saipen goal <objective>
```

enables Goal Mode.

SAIPEN:

1. records the goal;
2. builds or rebuilds the queue;
3. picks the next workable ticket;
4. executes it;
5. verifies;
6. reviews;
7. continues with the next one;
8. does not ask after every step: "Continue?"

There are safety limits on waves and ticket counts. Autonomy does not mean wandering the repository forever under the moon.

Goal Mode works until one of the honest outcomes:

```text
the goal is reached;
the work is blocked;
a safety valve fired;
the available volume of work is exhausted.
```

---

## 7. Find the next useful work on its own

When the ordinary backlog runs out, the Maintenance layer can enter a loop:

```text
HUNT
→ ADD
→ HUNT
```

### HUNT

Looks for:

* real defects;
* contradictions;
* broken checks;
* dead code;
* architectural drift;
* unguarded mandatory rules;
* mismatches between documentation and behavior.

### ADD

When no obvious defects remain, proposes the next natural feature that continues the existing architecture.

It does not throw a creative festival.

SAIPEN evolves step by step:

```text
existing pattern
→ obvious gap
→ minimal extension
→ verification
```

Not like this:

```text
the agent got bored
→ rewrote half the project in Rust
→ called it modern architecture
```

---

## 8. Distinguish audit from repair

SAIPEN separates several actions that models love to dump into one pot.

### `markhunt`

Runs a broad audit and records findings.

Fixes nothing.

That matters: first establish the fact, then change the project.

### `hunt`

Turns confirmed findings into proper tasks.

### `validate`

Checks the structural integrity of the SAIPEN state itself and repairs permitted damage.

### `test`

Runs the declared tests and reports PASS or FAIL.

Does not quietly fix the test while checking it.

### `clean`

Removes junk, cleans the board, and tidies the structure, but must check links and dependencies before moving or deleting files.

Because a file can look like an orphan until a program calls it at three in the morning.

---

## 9. Demand evidence instead of a pretty report

SAIPEN is built against typical LLM habits:

* claim a file was read when it was not;
* say the tests passed without running them;
* invent a plausible path;
* stop after the first green result;
* retell the task instead of doing it;
* take the user's last remark as the new truth of the project;
* turn a temporary assumption into a permanent rule.

That is why work leaves a trail:

```text
file change;
LOG event;
BOARD change;
STATE change;
command and its result;
verification evidence.
```

If the agent did nothing, it must say exactly that, not compose a report about great internal preparation.

In SAIPEN, the word "done" on its own weighs about as much as a store receipt without the item name.

---

## 10. Verify the protocol itself

SAIPEN has its own conformance layer.

It checks:

* state correctness;
* valid phase transitions;
* ticket shape;
* dependencies;
* event ordering;
* cross-document links;
* schema compliance;
* rule coverage by checks;
* behavior on PowerShell and shell;
* corruption and recovery scenarios;
* mutational red controls.

A check must be able to turn red when the rule is broken.

If a test is always green, it is not a test. It is a houseplant.

---

## 11. Survive interruptions and agent changes

SAIPEN uses checkpoints.

Before a dangerous transition the agent saves:

* the current phase;
* the active ticket;
* the completed part;
* verification results;
* the next step;
* the working directory state.

If the agent died, hung, hit the limit, or was closed, the next one does not start archaeological digs in the chat.

It reads the checkpoint and continues.

**継続 — keizoku — continuation.**

Not heroic memory recovery. A routine operation.

---

## 12. Never destroy someone else's unfinished work

A dirty Git tree is a normal project state for SAIPEN.

The agent must determine:

* which changes belong to its ticket;
* which were left by the user;
* which belong to other unfinished work;
* what can go into the current release;
* what must not be touched.

SAIPEN forbids:

* unexpected `reset`;
* rolling back other people's files;
* erasing uncommitted work;
* mass overwriting without verification;
* fake "cleaning" of the project by deleting things you do not understand.

The principle is simple:

> If you do not know whose it is — do not touch it with your paws.

---

## 13. Stop honestly

When the work genuinely cannot continue, SAIPEN uses an explicit `WAIT:` or moves the ticket to `BLOCKED`.

The reason must be concrete:

```text
manual review needed;
permission required for a destructive operation;
capability missing;
a mandatory decision is unknown;
first publish needed;
an external blocker exists;
a safety valve fired.
```

The agent must not guess.

But it also must not block out of its own laziness.

Lack of information — stop.
Unwillingness to look at a file — not a stop.

---

## 14. Show the real project status

The command:

```text
saipen status
```

works read-only.

It shows:

* the current phase;
* the active task;
* the next work;
* what waits for the user;
* which results are claimed but not yet proven;
* when the conformance check last ran;
* how stale the current state is;
* which tasks are blocked.

SAIPEN does not declare its own project "healthy" or "production ready".

It shows facts. The human draws the conclusion.

An agent that awarded itself a medal is still an agent that awarded itself a medal.

---

## 15. Hand work between specialized factories

SAIPEN supports isolated producer processes.

They work separately from the main tree and deliver results through `OUTBOX.md`.

Examples:

### `saihunt`

Finds defects and suspicious places.

A sensor. Not a repairman.

### `saitest`

Turns a suspicion into a reproducible fact or kills a false hypothesis.

It builds adversarial scenarios:

* wrong input;
* boundary values;
* broken ordering;
* repeated calls;
* corrupted state;
* resource pressure;
* hostile environment.

### `saipython`

Takes small Python defects, fixes a copy in an isolated workspace, verifies it, and hands over a ready patch.

It does not edit the main tree itself.

### `saitranslate`

Prepares the multilingual package separately from Core.

### `saiwiki`

Prepares documentation and a wiki package bound to a concrete state of the sources.

Core accepts only a fresh, verified, and complete package.

No:

> I sort of did something there, check the other chat.

Only payload, instructions, source commit, and evidence.

---

## 16. Run work through an industrial pipeline

The Crew Circuit command runs the project through a sequence:

```text
sense
→ reproduce
→ intake
→ build
→ verify
→ review
→ translate
→ document
→ publish
```

Each stage passes to the next not a promise, but:

```text
reproduction;
verdict;
ticket;
package;
evidence.
```

If a stage is empty — that is recorded as a result.

If a stage is blocked — the pipeline stops.

A partial result is not passed forward with a note "seems fine there".

The current Crew Circuit is sequential. A full concurrent Crew Mode with atomic claims, epochs, worktrees, and a release captain is being designed separately and is not presented as an already solved problem.

---

## 17. Save context

SAIPEN uses lazy loading.

The agent first reads the small BOOT kernel and the INDEX.

After that it loads only:

* the active phase document;
* the needed Core rule;
* the specialized document for the current work;
* the relevant durable project memory.

It does not have to reread the whole constitution, the history of the state, and the validator's family tree every session.

This reduces:

* token cost;
* the chance of distraction;
* conflicts between old instructions;
* the influence of irrelevant rules;
* cold-start time.

**Vähem müra, rohkem tööd.**
Less noise, more work.

---

## 18. Work without mandatory infrastructure

The foundation of SAIPEN:

```text
Markdown
Git
the file system
stdlib Python for the full validator
```

Without Python, a portable shell/PowerShell validation floor remains.

The project can be opened as an Obsidian vault.

`KNOWLEDGE/` is visible in the graph.
Ordinary links work.
The state is human-readable.
Git shows the whole history of changes.

No hidden magic.

If SAIPEN breaks, you can open it in a notepad and understand what happened.

That is what a system is called. Everything else is sometimes called a dashboard.

---

# Main commands

```text
saipen set                 adopt a project
saipen continue            continue the work
saipen plan                create a plan and tickets
saipen goal <text>         execute a goal autonomously
saipen status              show state, change nothing
saipen stop                save a checkpoint and stop
saipen hunt                look for defects
saipen markhunt            run a broad audit
saipen test                run the tests
saipen validate            check the structure
saipen clean               clean up the project
saipen prepare             prepare a handoff
saipen collect             accept a ready package
saipen translate           prepare translations
saipen ship                ship a release
saipen crew                run the full production cycle
```

For frequent actions there are short keys like:

```text
cc     continue
sss    show status
ss     save a checkpoint and stop
```

A command is the whole message. No four-paragraph incantation.

---

# What SAIPEN does not do

SAIPEN is not a new LLM.

It does not make a weak model brilliant.

It does not guarantee that an agent will never make a mistake.

It is not a distributed consensus algorithm for a hundred machines.

It does not replace tests, Git, and engineering thinking.

It must not store secrets or user data without need.

It does something else:

> Errors become visible.
> Work becomes continuable.
> State becomes checkable.
> Agents become replaceable.

---

# Who this is for

SAIPEN is useful if:

* you work with several AI coding agents;
* you constantly hit session limits;
* you switch models by price, availability, or task;
* you run a project longer than one conversation;
* you are tired of explaining the same thing to the agent;
* you want a task queue without a manual `continue` after every step;
* you want to see the difference between "done" and "proven";
* you do not trust the magic memory of a chat;
* you prefer open files over closed infrastructure;
* you want the project to outlive the death of any particular agent.

---

# In one sentence

**SAIPEN turns an AI from a forgetful conversationalist into a replaceable worker who walks into the shop, reads the project state, takes the next task, leaves evidence, and does not require you to retell the whole life of the factory.**

```text
The chat is gone.
The model changed.
The limit ran out.
The project did not forget.
```

**SAIPEN. One command. Zero dependencies. Zero amnesia.**
