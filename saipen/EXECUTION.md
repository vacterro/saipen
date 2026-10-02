# SAIPEN Execution Policy

Owns output/narration and ordering. STYLE owns voice; CORE owns lifecycle,
routing and safety.

<!-- RULE-OWNER: EXEC-HUSH-01 -->
<!-- RULE-OWNER: EXEC-RESPONSE-01 -->

## Precedence

`user/safety/CORE > execution policy > STYLE`

Higher layer wins. This policy decides whether text exists; STYLE then selects
language/voice. HUSH's non-suppressible set is below.

## Default response surface — EXEC-RESPONSE-01

Ordinary operational boundaries render vertically, NO prose before them:

    STATUS
    RESULT
    BLOCKER
    OPERATOR ACTION
    NEXT EXACT ACTION
    VALIDATION
    EFFICIENCY         (optional)
    DETAILS            (optional, LAST, omitted by default)

STATUS = compact ticket/phase/WAIT/BLOCKED/terminal. RESULT = outcome.
BLOCKER = `NONE` or exact canonical code + bounded reason. OPERATOR
ACTION = `NONE` or exact HUMAN action due now, never an agent command. NEXT
EXACT ACTION = EXACTLY ONE canonical command, manual action, or `NONE`; no
chain (`&&`, `||`, `;`) or "then". These fields are always present. VALIDATION
= bounded proof. EFFICIENCY = `saipen_engine.efficiency` KPI: APPROXIMATE,
final boundary, never quality or authority.

COMPACTNESS BUDGET (owned here, enforced in code; field CONTENT excludes
labels): LINES: RESULT <= 3, BLOCKER <= 1, OPERATOR ACTION <= 1, NEXT EXACT
ACTION <= 1, VALIDATION <= 5, EFFICIENCY <= 1, DETAILS <= 8. CHARS: STATUS <=
240, RESULT <= 720, BLOCKER <= 300, OPERATOR ACTION <= 300, NEXT EXACT ACTION
<= 240, VALIDATION <= 480, EFFICIENCY <= 240, DETAILS <= 2400, whole boundary
<= 2000 (4400 authorized). Code: `response_surface.FIELD_*_BUDGETS`; adapters
never repeat them; excess is refused.

DETAILS is absent by default; ordinary responses carrying it are REFUSED.
DETAILS AUTHORIZATION: `detail_mode` in `saipen_engine.response_surface`, closed set
NONE, EXPLICIT_REPORT, AUDIT, HANDOFF, EXCEPTIONAL_BOUNDARY. Transport:
`--detail-mode <mode>` or `--request <text>` (human ingress), never outgoing
prose. Direct affirmative requests qualify; incidental nouns, negations and
quoted examples do not. Ambiguous wording stays compact. Invalid modes are
refused by the owner, including direct checker/classifier calls.

Invariants: CONTROL SURFACE PRECEDES EXPLANATION; NO REQUIRED HUMAN ACTION MAY
EXIST ONLY IN FREE-FORM PROSE; THE HUMAN MUST NEVER HAVE TO READ AN ESSAY TO
DISCOVER WHETHER ACTION IS REQUIRED; WAIT without OPERATOR ACTION is invalid.

`saipen_engine.response_surface` renders/checks via `saipen response
render|check --stdin`. `--auto-eligibility --project-root <root>` rejects
premature handback.

RESPONSE ENFORCEMENT: per-host `response_enforcement` in
`extensions/adapters/registry.json`, separate from tool-only `declared_strength`.
MECHANICAL = final-message refusal hook, with `response_hook` in its own
`hook_artifact`; ADVISORY = instructions only; UNAVAILABLE = no response
surface. Never conflate these claims. Stop re-entry records its limitation
instead of looping. Mid-session activation binds on the init turn.

PROTOCOL ADMISSION (PROTOCOL-ADMISSION-01): `saipen_engine.protocol_admission`
owns admission; post-generation checks cannot grant it. Runtime fingerprints
bind project, BOOT, STYLE, EXECUTION, host activation, skill identities and hook.
Prose proves nothing. Changed proof/session/model/provider invalidates admission.
Binding -> ADMISSION -> EXEC-RESPONSE -> chat style; first failure decides
(`response_surface.gate_final_response`). Gate only visible output; authority
reads, skill resolution and init remain available. Ledger writes require
separated host authority and keyed provenance at the write boundary; SHA256
only detects corruption. T-1563 disables same-user signing and legacy provenance.
Claude admission is UNAVAILABLE and remains required.

CHAT STYLE GATE (T-1558): unmeasured ordinary chat let novels pass.
`saipen_engine.chat_style` COMPILES current STYLE.md: line maximum, Anti-Drift
Sentinels, `reply_language` pin. Uncompilable authority is refused, never defaulted.
Fenced code escapes prose measures, not the total ceiling. Violations yield
`CHAT_STYLE_DRIFT`. Only a human report/audit/handoff request (`detail_mode`,
from REQUEST, never reply) lifts the line budget. Hosts inject the generated
`saipen response style --json` contract, never a hand-written copy.

AUTONOMY (T-1416): OPERATOR ACTION NONE + executable canonical action + no true
response boundary -> continue execution; DO NOT return a status card.

## Default execution

Silent execution is ON by default: runnable work, tool calls and phase changes
produce no model-authored progress prose; continue autonomously and render one
compact final boundary. Required human action, safety, real blockers and
capability failures surface immediately. Higher-priority host instructions win;
no adapter claims silence it cannot enforce.

`hush.py` owns the policy (`saipen response policy --request TEXT`). Only an
affirmative progress request authorizes bounded intermediate chat, for that
ingress; continue/finish commands, quotations and negations do not.
`saipen response intermediate --stdin --request TEXT` refuses narration by
default and applies the STYLE budget when progress is authorized. Machine
status, tool activity, reasoning and host Thought UI are not commentary;
heartbeats go to logs, never chat. Registry
`execution_capabilities` records each host's real limits: Stop hooks cannot
retract streamed text.

PARALLEL LANE (T-1575): idling on a long gate wastes the agent; editing its
tree wastes the gate. Run it (core-unit family, full suite) in the background
and keep working: review the diff, write `.saipen/evidence/`, SCOUT queued
Work read-only, build the next change in a scratch copy. Await its completion
signal, never sleep-poll. A live marker adds `inflight` to `continue|status
--json`; the guard refuses in-root edits outside `.saipen/` (`TREE_UNDER_TEST`).

Transport: `saipen host entry` / BOOT Entry; a failed `python -m saipen` /
`where saipen` proves nothing, and inventing another invocation is not a recovery.

## HUSH

`hush <task>` applies only to that task and authorized continuations. Owner:
`tools/saipen_engine/hush.py`; projection: `saipen hush <task>`. Strip only the
LEADING modifier; pass `<task>` UNCHANGED to normal resolution. Suppress only
that route's output: `hush cc` routes as `cc`. Bare `hush` changes nothing and
is reported. TASK-LOCAL; never persisted to `STATE.md`.

- Tool-first silence: omit narration, plans and success chatter. Structured
  results/machine evidence are data.
- HUSH may suppress chatter/progress/DETAILS, never STATUS, BLOCKER, OPERATOR
  ACTION, NEXT EXACT ACTION or required VALIDATION. ONE response schema.
- Mandatory exceptions: safety/destructive confirmation, missing human
  authority, terminal failure, protocol corruption, externally visible side
  effects, and the final evidence report (<= 20 lines).

HUSH preserves source capture, coverage, LOG, findings, gate output and failure
diagnostics; ends at terminal result or explicit cancel.
