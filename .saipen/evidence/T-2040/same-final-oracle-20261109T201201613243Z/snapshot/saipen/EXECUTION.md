# SAIPEN Execution Policy

Priority: higher host instructions > user/safety/CORE > execution > STYLE.

<!-- RULE-OWNER: EXEC-RESPONSE-01 -->

## Default response surface — EXEC-RESPONSE-01

Chat is a CONTROL SURFACE: state -> typed facts -> bounded renderer ->
validation -> delivery. No model recap.
`saipen response digest --project-root ROOT --reason final|stop|status|summary|safety`
generates it. `response render|check --stdin` is the low-level diagnostic API;
`--classify --auto-eligibility --project-root ROOT` is the final gate.

INLINE `LABEL: value`, this order, no surrounding prose:

    STATUS
    RESULT
    BLOCKER
    OPERATOR ACTION
    NEXT EXACT ACTION
    VALIDATION
    EFFICIENCY   (optional)
    DETAILS      (authorized only, LAST)

STATUS: active phase/task or idle verdict. RESULT: outcome. BLOCKER:
CODE -- reason. OPERATOR ACTION: exact HUMAN decision, never agent command.
NEXT EXACT ACTION: ONE command/action or NONE; no chains/vague advice.
BLOCKER/ACTION NONE are omitted, parse as NONE. VALIDATION: conformance/test
aggregates. EFFICIENCY: final approximate KPI, never quality/authority.

RESPONSE REASONS, actual rendered weight (labels, blanks, fences included):
SILENT_CONTINUATION 0/0; COMPACT_FINAL and STOP_HANDBACK <= 6 lines/900 chars;
HUMAN_ACTION_BLOCKER and SAFETY_BOUNDARY <= 8/1200;
EXPLICIT_DETAILED_REPORT <= 16/3600.
Field nonempty content lines/chars:
STATUS 1/64; RESULT 1/300; BLOCKER 1/300; OPERATOR ACTION 1/300;
NEXT EXACT ACTION 1/240; VALIDATION 1/160; EFFICIENCY 1/240; DETAILS 8/2400.
Maxima are not filling grants. Code: `response_surface.REASON_BUDGETS` and
`FIELD_*_BUDGETS`. Legacy vertical records still pay visible limits. Overflow
is `OPERATOR_OUTPUT_OVERFLOW` data; failure returns a compact failure digest,
NEVER the oversized original, kept by `response preserve`.

One fact, one field: completion RESULT; validation VALIDATION; blocker BLOCKER;
decision ACTION; execution position NEXT. Root cause belongs in evidence or
authorized DETAILS; never logs/overflow. Inventories: LOG/state/evidence.
Chat: O(1) counts/categories. STOP preserves execution position in its handback.

DETAILS forbidden by default, bar one reference line. Only witnessed HUMAN depth
grants EXPLICIT_REPORT/
AUDIT/HANDOFF: closed affirmative whole-clause EN/ET/RU grammars. Summary/brief/
quick update/ordinary final report stay compact. Negation/quotation/nesting/
incidental phrases and model reasoning grant NOTHING. `--detail-mode` is
diagnostic, not authority; EXCEPTIONAL_BOUNDARY legacy only. Language is separate.
Explicit copy-ready handoffs/audits/specs/inventories are typed artifacts with
a separate bounded carrier; preserve requested documents. Outgoing fences/
DETAILS/filenames grant nothing. Raw logs reference actual files; chat stays small.

SRC-199: diagnosis is no task inventory. Cite request, observations, rule/owner,
cause or justified unknown, correction. Preserve legitimate refusals and
ingress/host uncertainty. `response_surface` checks structure/citations only;
independent review owns meaning. FreeBuff: ADVISORY.

Control facts first; human action has a field. WAIT needs ACTION.
Runnable work continues SILENTLY absent a true boundary.
Continuation discipline: an agent that has named the next exact action must
execute it in the same turn tool-to-tool. A turn whose NEXT EXACT ACTION is an
executable command the engine could run continues tool-to-tool; a COMPACT_FINAL
handback that names its own NEXT EXACT ACTION and then stops, offering it again
as an optional follow-up card, is protocol drift (AUTONOMOUS_HANDBACK -- it makes
the operator click what the agent already knew how to do). Only a real WAIT/
operator gate (OPERATOR ACTION due), a true WAIT_EXTERNAL or a terminal result
ends the turn.

## Enforcement and admission

<!-- RULE-OWNER: OPERATOR-QUESTION-01 -->

Interactive Question/AskUser calls are operational control handbacks. Only
canonical `automation.operator_action_due: true` permits one; known schema and
disposition are required. CONTINUE without that flag means execute `cc`, read
`load_path` and perform its action in the same turn. COMPLETE renders completion;
WAIT_EXTERNAL/BLOCKED/INVALID render their canonical diagnostic, never a menu.
Session loss, keeper completion and uncertainty grant no authority. Recover
project memory; BUILD stays BUILD. T-1619 owns bounded executor failover.

`response_surface.gate_operator_question` consumes the existing status/response
owners through `guard --event-json -`. A true human boundary permits exactly
its canonical operator action; no typed choices means no invented menu. Use
`response digest` if a widget cannot represent it. Safety/product clarification
retain actual authorization and higher host priority. Unbound projects remain
non-interfering; corrupt canonical state gets a diagnostic, never guessed work.

Registry `question_enforcement` is capability, separate from installed proof:
OpenCode `tool.execute.before` and Claude question-only `PreToolUse` refuse
before delivery; that matcher excludes bootstrap/read/shell tools. Others use
available instructions/final guards, ADVISORY; no FreeBuff UI refusal is proved.
Adapters transport the decision, never a separate remaining-work predicate.

`response_surface` owns renderer/classifier/delivery; adapters transport.
`extensions/adapters/registry.json` separates tool/admission/final/style/
intermediate capabilities.
MECHANICAL: completed-part replacement/refusal or ONE post-render Stop correction,
not invisible prevention. ADVISORY: instructions. UNAVAILABLE: no surface.
Post-render hooks cannot retract visible/streamed text. Stop re-entry records
its limitation, never loops/claims fail-closed. Source/installed/loaded hashes,
active config and trust are separate facts; mid-session init binds this turn.

PROTOCOL-ADMISSION-01: binding -> ADMISSION -> EXEC_RESPONSE -> CHAT_STYLE;
first failure wins. `protocol_admission` binds project/BOOT/STYLE/EXECUTION,
host/skill/hook. Changed proof/session/model/provider invalidates admission.
Prose proves none; bootstrap/skill/init remain reachable. Ledger writes need
separated host authority/keyed provenance; SHA256 proves only integrity.
T-1563 stands: same-user signing and legacy provenance stay disabled. The
separated owner is the host-authority broker: it proves the host's own hook
invocation from the OS and owns the ledger write; only a session it ADMITTED
is MECHANICAL. HOST-INTEGRATION-01: an unproven session is a `host_taxonomy`
code, never prose -- a gap runs DEGRADED/UNVERIFIED by default (STRICT is
operator opt-in: `saipen host mode`), a conflict blocks in every mode.
Post-generation checks never grant admission.

`chat_style` compiles STYLE lines/language/sentinels; failure never guesses.
Fences escape prose/language, not total weight. Violations: CHAT_STYLE_DRIFT.
Hosts inject `saipen response style --json`, not their own contract.

<!-- RULE-OWNER: EXEC-HUSH-01 -->

## Default execution and HUSH

Runnable work emits no discretionary progress. Decisions/safety/destructive
confirmation/terminal failures/blockers/corruption/external effects surface
immediately. Higher host narration wins; no unsupported silence claims.
`hush.for_request` / `response policy --request TEXT` accepts only an explicit
affirmative progress request for THIS ingress, never a permanent grant.
`response intermediate --stdin --request TEXT` suppresses by default; authorized
progress is STYLE-bounded. Runtime heartbeat goes to LOG/status/telemetry/UI,
not chat. Tool data, host Thought UI and reasoning are separate surfaces.

`hush <task>` is task-local, never STATE. Strip only the leading modifier;
route unchanged task. Bare hush changes nothing. Suppress narration/plans/
success chatter/optional DETAILS, never safety/authority/corruption/terminal
failure/final digest. SAME reason budget.
All evidence/safety/lifecycle/recovery survive; end at terminal result/cancel.

PARALLEL LANE (T-1575): background long gates; read-only review/evidence/scratch
work meanwhile. Never edit frozen subject. Await completion signals; live
inflight blocks in-root edits outside .saipen/: TREE_UNDER_TEST. No sleep-poll.

Transport: BOOT Entry / `saipen host entry`; a failed `python -m saipen` or
PATH probe proves nothing; inventing another invocation is not a recovery.
