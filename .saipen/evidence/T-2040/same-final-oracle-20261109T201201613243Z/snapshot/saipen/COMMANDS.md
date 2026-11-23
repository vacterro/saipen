# SAIPEN Command Surface

This file owns command semantics; `REGISTRY.json` owns machine facts.
Runtime never parses this prose. CORE owns only global authority and
deterministic priority rules.

## Shortcut table

<!-- RULE-OWNER: CMD-ROUTING-01 -->

Resolve shortcuts mechanically from REGISTRY.json before acting. The complete
[alias inventory](COMMANDS_REFERENCE.md) is conditional reference material.
`gg` creates a new objective; `cc` resumes (arguments never create a goal).
`ccc` converges to ship and refreshes J-M. Confirmation/cut and producer
contracts remain with their existing owners; an alias grants no authority.

## Canonical command forms

The full API inventory is the conditional [command reference](COMMANDS_REFERENCE.md).
Ordinary resolution uses the CLI's structured route and REGISTRY.json.
The appendix grants no authority or recursive owner loads.
`commands.resume` prevents the measured `cc all` -> goal-usage misroute:
bare resume and `all` share the existing pipeline; neither creates a goal,
and publication/authority renewal retain their existing proof gates.

FUTURE-GATE-01 verbs (FUTURE.md owns the rules; every mutating verb is
published here and declared in COMMAND_EFFECTS.json):

| Command | Phase / Action |
|---------|---------------|
| `saipen future [status\|list\|next]` | DIAGNOSTIC: lifecycle counts, per-gate verdicts and the ONE deterministic next candidate; writes nothing |
| `saipen future refresh` | EXECUTION: rebuild `.saipen/future/index.json` by identity (id > digest > title, never filename alone); routing runs it whenever the projection is not CURRENT |
| `saipen future refine FG-#### [--slice TEXT --evidence PATH[,PATH]]` | EXECUTION: classify ONE ambiguous gate into the closed vocabulary and bind its verdict; never rewrites the original, never grants authority |
| `saipen future promote FG-####` | INGRESS: promote ONE bounded slice of an ELIGIBLE gate through the same ingress `saipen start` uses; refuses an ineligible or already-owned gate |
| `saipen future add <title> [--body TEXT] [--priority P0-P3] [--evidence PATH[,PATH]]` | INGRESS: record a deferred candidate, DEFERRED by default; never Work, a rule source or authority by itself |

`clean_execution`: CLEAN = `PENDING`; DONE with `RUN: clean -> done @HASH` =
`COMPLETED`; else `UNPROVEN`.

`saipen validate` first checks `.saipen/STATE.md`, `BOARD.md` and `LOG.md`;
malformed input refuses before execution. It then runs this runtime's
`tools/validate.py --project-root <project> --gate core` as argv, without a
shell. Its sole write is a receipt; product files, Work/phase, intake and
Improve stay untouched. Only durable CURRENT_PASS yields VALID; exit 0 alone
proves nothing.

CURRENT_FAIL retains blocking findings; ENGINEERING_REQUIRED has no next command.

`launch <host>` requires global `--agent` (`ACTOR_UNBOUND` otherwise).
It exports actor, resolved root and portable lineage before the host; arguments
follow `--`. Generic launches inherit `STATE.agent`; no manual seat.
A host session id is never an actor.

## Compound parsing

<!-- RULE-OWNER: CMD-COMPOUND-01 -->

- Segments separated by ` + ` (space-plus-space) or newlines.
- Quoted payload (`"..."`) is opaque and never split.
- STOP_ON_FAILURE by default: a later segment after an earlier REFUSED/FAILED
  becomes NOT_RUN unless provably independent.
- `saipen push + build ccc` executes both segments in order.
- Launchers pass decoded argv intact: bare `+` splits, `\+` is literal,
  `--` ends splitting (`.cmd` removes `"+"` quote marks).
- `hush <task>` applies execution policy `EXEC-HUSH-01`; `hush` is syntax,
  never a lifecycle or style owner.

## Unicode twin normalization

Cyrillic shortcuts are the same as Latin. Codepoint substitution:
`а→a е→e о→o р→p с→c у→y х→x`. Latin `st`/`sss` have no Cyrillic twin.
Cyrillic `сс` → Latin `cc` (continue), never `st` (stop) or retired `ss`.
Retired `ss` returns `SHORTCUT_RETIRED` with non-success and zero mutation;
use `st` to checkpoint and stop, or `sss` for read-only status.

## Continue→improve fallthrough

<!-- RULE-OWNER: CMD-CONTINUE-01 -->

**Skill-only no-op is not continuation.** BOOT -> `saipen continue --json` ->
read `load_path` -> execute `action` now. Read missing state; never ask what `cc`
means or offer phase menus. Questions: EXECUTION OPERATOR-QUESTION-01.
Clean Git proves no BOARD completion.

**Auto-Doctor (SRC-253 stage 3).** Defect: stale conformance strands `cc`.
`STALE_PASS`/`NOT_RUN`/`VALIDATOR_VERSION_MISMATCH`: canonical validation once
per chain; require success, durable `CURRENT_PASS`, fresh route. Resume this
invocation with Doctor proof. Other refusals retain owners. Read-only,
`next`, dry-run: no repair. No new authority.

`saipen continue` routes: recovery -> WAIT -> active phase-owned continuation
-> queued explicit user Source -> Audit Inbox -> ordinary BOARD Pick Rule ->
maintenance -> bounded Improve fallback. A queued Source stage means the
oldest unprojected `user_instruction` receipt (T-1436): a request captured
while the seat was busy is started through `saipen start --receipt SRC-###` by
the next canonical poll after the seat frees -- an operator never retypes the
command, and the queued request outranks persisted converge intent and
speculative backlog. Audit Inbox (SOURCES.md): numbered layers precede TODO;
fresh named drops follow workable BOARD. Active Work wins; workable inbox
forbids idle/Improve. Generation = path+digest; changed bytes are NEW.

Every `continue`/`cc`/`status` JSON answer carries `telegrams`: the acting
seat's unread SAIMAIL telegram COUNTS when a mailbox is bound and
`saimail-local` is on PATH (else `NOT_CONFIGURED`/`UNAVAILABLE`). Report a
nonzero count; reading is `read_command`, opening is an explicit decision. A
telegram never routes, creates Work or skips a WAIT (T-1497).

A mailbox is bound through exactly one resolution order (SRC-136, T-1557):
an explicit `SAIMAIL_WORKSPACE` always wins, else the per-user default root
(`%LOCALAPPDATA%/saipen/saimail` on Windows, `~/.local/state/saipen/saimail`
elsewhere) when SAIMAIL has already initialized it. `saipen mail init` is the
one canonical provisioning verb: it runs `saimail-local saipen init` against
the default root for the acting seat, idempotently, and writes nothing inside
any project. `saipen init` attaches the same default mailbox for a genuinely
new user when SAIMAIL is installed and nothing is bound yet -- an attachment
reported as data, never a dependency of INIT. SAIMAIL carries internal
letters only; electronic mail is not part of this binding.

After the Pick Rule and before any idle verdict, two inbox diagnostics are
restated rather than routed: `audit-inbox-invalid` (a layer that cannot be
read) and `audit-inbox-residue` (every layer settled and deleted, but
`audit/` still holds entries SAIPEN never captured). Neither outranks workable
BOARD Work; neither is ever deleted automatically.

`saipen continue` falls through to `saipen improve` ONCE after recovery,
blocked, queued, audit-inbox and required-follow-up routing is exhausted. An
already-active prepared cycle is resumed, never duplicated. A
completed/archived cycle allows fresh discovery. No unbounded improve
carousel.
