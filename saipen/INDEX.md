# SAIPEN INDEX

This index describes all available SAIPEN documents. Agents MUST NOT read these documents blindly. Read only the specific document required to answer your current rule question or execute your current phase. Reading the full protocol indiscriminately is a violation (T-491: Lazy Load).

## Core Protocol
- `BOOT.md`: Cold-start kernel. Boot sequence, environment binding, and global constraints. You just read this.
- `STYLE.md`: Voice, tone, and compression contract (caveman-ded). Read automatically during BOOT.
- `CORE.md`: The main protocol rules (formerly RFC.md). Covers commands, state lifecycle, transition table, verification rules, and agent constraints. Load only if you have a specific rule question not answered by the phase document, or if BOOT.md step 7 sends you to §1.10 for command/shortcut resolution.
- `MAINTENANCE.md`: Maintenance and recovery logic. Load only when executing `clean` or `audit`, or recovering from project corruption.
- `RFC.md`: Compatibility redirect only. The constitution was split into CORE.md and MAINTENANCE.md in v7.190.0. This file is a three-line stub; never treat it as authoritative.

## Phase Documents (`phases/*.md`)
Keep exactly one phase document loaded at a time. Replace it immediately when the active phase changes.
- `init.md`: Bootstrap `.saipen/` for a new project.
- `plan.md`: Turn request/backlog into tickets.
- `scout.md`: Claim ticket, explore codebase.
- `build.md`: Execute code/prose modifications.
- `verify.md`: Testing, validation, and checklist review.
- `review.md`: Automated checks and formatting.
- `ship.md`: Git commit, push, and release.
- `done.md`: Finalize tickets, end session.
- `add.md`: Plan new features (evolutionary, minimal delta).
- `hunt.md`: Defect/improvement sweep (6 categories).
- `markhunt.md`: Dry uncapped audit, records only.
- `clean.md`: Repo scrub, board pruning.
- `blocked.md`: Handle blocked tickets.
- `translate.md`: Isolated 32-language translation factory.
- `prepare.md`: Package work for handoff.
- `validate.md`: Conformance check + repair.

## Specialized Documents
- `UI.md`: Rules for UI/frontend work. Load ONLY when touching UI code.
- `HABITS.md`: Known failure patterns of modern LLMs and protocol countermeasures.
- `CONFORMANCE.md`: Excluded surface. NEVER read unless explicitly debugging a validator failure.
- `SKILL.md`: SAIPEN loader logic (do not read).

## Project Data
- `KNOWLEDGE/*.md`: Discovered architectural truths about the project. (Located in project root).
- `CHANGELOG.md`: Release notes history. (Located in project root).
