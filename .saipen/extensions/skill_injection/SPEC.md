# Skill Injection Lifecycle Contract

This document defines a deterministic lifecycle for injecting specialized
skill context into an agent session at runtime. It is a contract between
the agent's base execution context and any domain-specific skill that may
be loaded, retained, replaced, or ejected during a task.

## 1. Problem Class Identification

A problem class is identified from evidence present in the task at hand,
never from guesswork.

**Minimum evidence.** At least TWO of the following MUST match the same domain
before a candidate skill is considered:

1. The task description names a domain-specific technology, framework, or
   protocol (e.g. "react component", "database migration", "pdf extraction").
2. A file path in the task scope has an extension, import, or shebang
   associated with the domain (e.g. `.tsx`, `import React`, `#!/usr/bin/env python`).
3. A command the user explicitly invoked or the project's declared harness
   names a domain-specific tool (e.g. `next build`, `alembic upgrade`).
4. The active ticket, project README, or a `KNOWLEDGE/` file explicitly
   declares the domain as the project's primary surface.

The evidence set is conjunctive at threshold 2: one signal alone is not enough,
because a `.py` file in a React project is still Python but the task is not.

**Disputed domain.** When two or more candidate domains each meet the threshold,
resolution (section 5) decides; neither is silently dropped.

## 2. Candidate Skill Selection

Each candidate skill carries a declared domain list and a token budget.

**Matching.** A skill matches when its declared domain list intersects the
identified problem class from section 1, AND its token budget (in words)
leaves at least the base context's own minimum free headroom. A skill whose
budget would overflow the context window is never selected.

**Smallest-first.** Among matching skills, the one with the smallest token
budget is loaded. If two skills share the same budget, the one declared first
in the skill registry is selected.

**No match.** When no skill matches, the agent proceeds with its base context
alone. A missing skill is never an error, and the system MUST NOT fabricate
one from pattern matching alone.

## 3. Injection Rules

When a skill is injected, its content is appended to the agent's context
under a fixed header that names the skill, its version, and the evidence
that triggered it.

**What a skill may add.** A skill's injected content is limited to:

- Domain-specific tooling instructions (build commands, test runners, linters).
- Idiomatic patterns and conventions for the domain (file layout, naming).
- Safety constraints specific to the domain (e.g. "never use raw SQL", "prefer
  `useMemo` over `useEffect` for derived state").
- Verification criteria the domain recognizes (e.g. "a react component test
  renders without warnings").

**What a skill MUST NOT add or override.** A skill is advisory and domain-scoped.
It MUST NOT:

- Alter the state machine (`STATE.phase`, `next_action`).
- Redefine or contradict any rule in `RFC.md`, `CORE.md`, `MAINTENANCE.md`,
  `BOOT.md`, `STYLE.md`, or the active phase document.
- Claim authority over a record the protocol owns (`BOARD.md`, `LOG.md`,
  `STATE.md`).
- Add a new phase, command verb, or transition.
- Change the confirmation gates for destructive operations (RFC § 1.1).

**Base protocol outranks.** If any injected text contradicts a base protocol
rule, the base rule wins silently -- the skill text is treated as absent for
that instruction. The conflict is logged as a `DEC` line naming the skill and
the superseded instruction.

## 4. Retain

A skill remains active as long as the problem class it was loaded for persists.
Persistence is measured by the same evidence set from section 1: when the
next ticket's scope still matches at least one signal from the original
evidence class, the skill is retained without re-evaluation.

Retention costs zero overhead: the skill is already in context and the next
ticket re-uses it without a new injection cycle.

## 5. Conflict Resolution

When two or more candidate skills both match the same task (disjoint domain
lists, each meeting the threshold from section 1), resolution is deterministic:

1. **Smallest budget first**, same as selection.
2. **Equal budget: declaration order** in the skill registry.

The agent loads exactly one skill. The losing candidate is recorded in the
injection LOG line (`H:` taxonomy, naming the winner, the loser, and the
evidence for each) so a human can re-prioritize the registry later.

Two skills whose domain lists overlap partially are NOT in conflict: the
overlapping domain is assigned to the smaller skill, and the larger skill
is dropped for this task. Overlap is measured by the intersection of the
declared domain lists, not by the skill content.

## 6. Replace

A skill is replaced when the evidence threshold shifts during a task.

**Trigger.** The active ticket's scope or the agent's next action changes
in a way that section 1 would now match a DIFFERENT domain with higher
confidence than the current one. Confidence is measured by signal count:
a domain with 3 matching signals replaces one with 2.

**Mechanism.** The current skill's injected content is removed from context.
The replacement skill is injected under section 3's rules, and a `DEC` line
records the transition: old skill, new skill, and the evidence delta.

The agent's canonical state (`STATE.md`, `BOARD.md`, `LOG.md`, `next_action`,
evidence gathered so far) survives the replacement intact. Only the injected
skill context is swapped.

## 7. Eject

A skill is ejected when the task no longer matches the domain it was loaded for.

**Trigger.** The next ticket's scope satisfies ZERO of the signals from the
original injection evidence set. It is not enough that the current task is
done -- the next task must demonstrably belong to a different domain.

**Mechanism.** The injected skill content is removed from context. A `DEC`
line records the ejection: the skill name, the evidence that loaded it, and
the evidence that ended it.

**Post-eject invariant.** After ejection, the agent's context MUST be byte-
identical to what it would have been had the skill never been loaded, except
for the LOG lines recording injection and ejection. No silent mutation of
base context survives ejection.

## 8. Verification of Specialist Context

Before ejecting a skill, the agent verifies that the specialist context is
no longer needed.

**Test.** The active `next_action` and ticket scope are run through section 1's
identification rules. If the result is the empty set (no domain matches), the
specialist context is confirmed unnecessary and ejection proceeds. If any
signal still matches, the skill is retained and the ejection is aborted.

**Verification failure.** When ejection is aborted, the skill stays in context
and a `H:` line records the retained domain signals. The agent does NOT
unload and immediately re-load the same skill -- that is thrash.

## 9. Invariants

1. **Determinism.** The same task, skill registry, and evidence always produce
   the same injection decision. Time, load, and the agent's own prior reasoning
   have no effect.
2. **No fabrication.** A problem class that matches no skill does not produce
   one. The empty set means base context only.
3. **Canonical state survives.** Inject, retain, replace, and eject touch only
   the injected skill context. `STATE.md`, `BOARD.md`, `LOG.md`, `next_action`,
   and `kitchen/` contents are never altered by the skill lifecycle.
4. **Base rules outrank.** Protocol rules always win over injected skill text.
   No skill may weaken a MUST, relax a cap, or re-interpret a gate.
5. **Auditability.** Every injection, replacement, and ejection produces a LOG
   line (`H:` taxonomy for injection/verification decisions, `DEC:` for
   lifecycle transitions) naming the skill, the evidence, and the outcome.
