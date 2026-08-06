# SAIPEN INDEX

This index describes all available SAIPEN documents. Agents MUST NOT read these documents blindly. Read only the specific document required to answer your current rule question or execute your current phase. Reading the full protocol indiscriminately is a violation (T-491: Lazy Load).

## Core Protocol
- `BOOT.md`: Cold-start kernel. Boot sequence, environment binding, and global constraints. You just read this.
- `STYLE.md`: Voice, tone, and compression contract (caveman-ded). Read automatically during BOOT.
- `CORE.md`: The main protocol rules (formerly RFC.md). Covers commands, state lifecycle, transition table, verification rules, and agent constraints. Load only if you have a specific rule question not answered by the phase document, or if BOOT.md step 7 sends you to §1.10 for command/shortcut resolution.
- `MAINTENANCE.md`: Maintenance and recovery logic. Load only when executing `clean` or `audit`, or recovering from project corruption.

## Phase Documents (`saipen/phases/*.md`)
Load **ONLY ONE** active phase document per turn (`<saipen_home>/phases/<phase>.md`).
- `scout.md`: Ticket claim and codebase exploration.
- `build.md`: Execution of code/prose modifications.
- `verify.md`: Testing, validation, and checklist review.
- `review.md`: Automated checks and formatting.
- `ship.md`: Git commit, push, and release.
- `done.md`: Finalizing tickets and ending the session.
- `add.md`: Planning new features (leads to PLAN).
- `plan.md`: Creating technical plans and breaking them into tickets.
- `markhunt.md`: Automated discovery of errors (generates HUNT tickets).
- `hunt.md`: Triage of discovered errors into TODO tickets.
- `clean.md`: Repository cleanup and board pruning.
- `translate.md`: Syncing localization guides.
- `blocked.md`: Handling tickets that cannot proceed.
- `abandon.md`: Terminating invalid tickets.
- `audit.md`: Auditing SAIPEN integrity.

## Specialized Documents
- `UI.md`: Rules specifically for UI/frontend work. Load ONLY when touching UI code.
- `HABITS.md`: Known failure patterns of modern LLMs and protocol countermeasures.
- `CONFORMANCE.md`: Excluded surface. NEVER read unless explicitly debugging a validator failure.
- `SKILL.md`: SAIPEN loader logic (do not read).

## Project Data
- `KNOWLEDGE/*.md`: Discovered architectural truths about the project. (Located in project root).
- `CHANGELOG.md`: Release notes history. (Located in project root).
