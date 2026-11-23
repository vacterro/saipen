# SAIPEN Execution Policy

Owns output/narration policy: what text exists, in what order. Not lifecycle,
routing, safety, or chat voice (STYLE owns voice).

<!-- RULE-OWNER: EXEC-HUSH-01 -->
<!-- RULE-OWNER: EXEC-RESPONSE-01 -->

## Precedence

`user/safety/CORE > execution policy > STYLE`

A higher layer wins. STYLE selects language/voice only after this policy decides
whether text exists. HUSH's non-suppressible set is listed under HUSH below.

## Default response surface — EXEC-RESPONSE-01

Every ordinary user-facing operational boundary renders vertically, in this
order, NO prose before it:

    STATUS
    RESULT
    BLOCKER
    OPERATOR ACTION
    NEXT EXACT ACTION
    VALIDATION
    DETAILS            (optional, LAST, omitted by default)

STATUS = compact ticket/phase/WAIT/BLOCKED/terminal. RESULT = what happened,
1-3 short lines. BLOCKER = always present: `NONE` or the exact canonical blocker
code + one bounded reason. OPERATOR ACTION = always present: `NONE` or the exact
HUMAN action required now (never an agent-executable command). NEXT EXACT
ACTION = always present: EXACTLY ONE action -- one canonical command, one
manual action, or `NONE`; never a chain (`&&`, `||`, `;`), never "then".
VALIDATION = bounded proof.

COMPACTNESS BUDGET (ONE owner: this document; the checker enforces; bounds are
over each field's CONTENT, labels excluded): LINES: RESULT <= 3, BLOCKER <= 1,
OPERATOR ACTION <= 1, NEXT EXACT ACTION <= 1, VALIDATION <= 5, DETAILS <= 8.
CHARACTERS: STATUS <= 240, RESULT <= 720, BLOCKER <= 300, OPERATOR ACTION <= 300,
NEXT EXACT ACTION <= 240, VALIDATION <= 480, DETAILS <= 2400, whole rendered
boundary <= 2000 (4400 authorized). The budgets and ceilings live in code as
`saipen_engine.response_surface` FIELD_LINE_BUDGETS/FIELD_CHAR_BUDGETS; no
adapter repeats them; over budget is refused, not trimmed.

DETAILS is absent by default: an ordinary response carrying it is REFUSED,
never an overflow bucket. DETAILS AUTHORIZATION is one machine fact,
`detail_mode` (`saipen_engine.response_surface`; closed set NONE, EXPLICIT_REPORT,
AUDIT, HANDOFF, EXCEPTIONAL_BOUNDARY), arriving as `--detail-mode <mode>` or
`--request <text>` (the human's request, classified by the owner), never from
the outgoing prose.

Invariants: CONTROL SURFACE PRECEDES EXPLANATION; NO REQUIRED HUMAN ACTION MAY
EXIST ONLY IN FREE-FORM PROSE; THE HUMAN MUST NEVER HAVE TO READ AN ESSAY TO
DISCOVER WHETHER ACTION IS REQUIRED; WAIT without OPERATOR ACTION is invalid.

`saipen_engine.response_surface` owns rendering and checking; hosts call
`saipen response render|check --stdin`, and `--auto-eligibility --project-root
<root>` rejects premature handback.

RESPONSE ENFORCEMENT is per host in `extensions/adapters/registry.json` as
`response_enforcement`, separate from `declared_strength` (tool refusal only);
never report one as the other. MECHANICAL = a host hook can refuse the outgoing
final message (needs a `response_hook` token in the host's own `hook_artifact`);
ADVISORY = instructions only; UNAVAILABLE = no final-response surface. A Stop
already in continuation records the honest re-entry boundary instead of looping;
a host that became SAIPEN mid-session is bound on the turn that ran the init.

PROTOCOL ADMISSION (PROTOCOL-ADMISSION-01): `saipen_engine.protocol_admission`
owns admission; post-generation checks cannot grant it. Runtime-delivered
fingerprints bind project, BOOT, STYLE, EXECUTION, host activation, skills by
identity and host hook. Prose proves nothing; any change to a proof, session,
model or provider invalidates the token. Binding -> ADMISSION -> EXEC-RESPONSE -> chat style;
first failure decides (`response_surface.gate_final_response`). Only user-visible
output is gated; authority reads, skill resolution and init remain available.
Ledger writes require separated host authority at the write boundary and keyed
provenance; SHA256 detects corruption only. T-1563 disables same-user signing
and legacy provenance. Claude admission is UNAVAILABLE and remains required.

CHAT STYLE GATE (T-1558): a reply that was not an operational boundary was never
measured, so the prose novel passed a green gate. `saipen_engine.chat_style`
measures a contract COMPILED from the current STYLE.md (line maximum, Anti-Drift
Sentinels, `reply_language` pin; an uncompilable STYLE.md is refused, never
defaulted); fenced code is outside the prose measures, inside a total ceiling.
`classify_final_response` returns `CHAT_STYLE_DRIFT` for ordinary chat that
breaks it; only the human's own report/audit/handoff request (`detail_mode`,
from the REQUEST, never the reply) lifts the line budget. `saipen response
style --json` prints the generated contract; a host injects that, never a
hand-written copy.

AUTONOMY (preserves T-1416): if OPERATOR ACTION is NONE, a canonically
executable action remains, and no true response boundary exists, DO NOT return
to the user -- continue execution instead of emitting a status card.

## Default execution

Prefer action and evidence over narrating each tool call; the control surface
(or none) replaces per-step commentary. Report failures when they occur;
continue autonomously when the repair is authorized and deterministic.

A command is logical; its transport is resolved (`saipen host entry`, BOOT.md
Entry). A failed `python -m saipen` or `where saipen` proves nothing, and
inventing another invocation is not a recovery.

## HUSH

`hush <task>` applies to that task and its authorized continuation chain.
Runtime `tools/saipen_engine/hush.py`; `saipen hush <task>` is its projection.
Modifier is stripped, `<task>` reaches the normal resolver UNCHANGED, and only
that route's output is suppressed. `hush cc` routes where `cc` routes. Only a
LEADING token is the modifier; a bare `hush` modifies nothing and is reported.
The policy is TASK-LOCAL, never written to `STATE.md`.

- Tool-first; silence lock: omit progress narration, plans, success chatter.
  Structured results and machine evidence are data, not narration.
- HUSH may suppress chatter, progress prose and DETAILS. It may NOT suppress
  STATUS, BLOCKER, OPERATOR ACTION, NEXT EXACT ACTION, or required VALIDATION --
  ONE response schema only.
- Mandatory exceptions: safety/destructive confirmation, missing human
  authority, terminal failure, protocol corruption, externally visible side
  effects, and the final evidence report (<= 20 lines).

Audits remain lossless: HUSH suppresses chat noise, never source capture,
coverage, LOG evidence, findings, gate test output, or failure diagnostics.
HUSH ends at a terminal result or explicit cancel.
