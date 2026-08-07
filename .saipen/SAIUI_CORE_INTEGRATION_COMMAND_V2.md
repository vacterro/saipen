# Command: ship `saiui` as a first-class built-in SubSaipen role

```text
saipen goal "Ship saiui as a first-class built-in fixer-type SubSaipen role for UI-only work, governed by the canonical Vintage Golden UI specification, with deterministic role loading, sandboxed patch handoff, validation, and a separate SAISENT target mission."

USER AUTHORIZATION
This message is explicit authorization to pivot to the objective above and execute it through the normal SAIPEN gates.
Do not ask for confirmation.
Do not bypass any destructive-operation, review, verification, or publish gate.

CURRENT-STATE SAFETY
Before pivoting:
1. Read the current `.saipen/STATE.md`, `.saipen/BOARD.md`, and LOG tail.
2. If any ticket is in `## DOING`, checkpoint it exactly as RFC requires before a phase-switching command.
3. Preserve its claim, evidence, and resumable `next_action`; do not overwrite, close, or silently abandon it.
4. The supplied snapshot has T-399 in flight, but trust the live files rather than this sentence if HEAD has moved.

REPOSITORY REALITY
This repository is the SAIPEN protocol repository, not the SAISENT application repository.
No SAISENT UI implementation is present here.
Therefore:
- implement and ship the reusable `saiui` role here;
- do not claim that SAISENT was audited or patched;
- produce a separate target-project mission artifact for later execution inside the actual SAISENT repository.

ARCHITECTURAL DECISION
`saiui` is a built-in fixer-type SubSaipen specialized in user interfaces.
It follows `extensions/subs/PROTOCOL.md`, including the one-door OUTBOX boundary and fixer pen model.

Its authority is deliberately asymmetric:
- inside its own `kitchen/pen/`: full authority to restructure or rebuild UI code when evidence justifies it;
- over the main project tree: read-only;
- over Core/backend semantics: zero authority;
- over integration: zero authority; Core alone collects, applies, verifies, reviews, and ships.

The canonical visual specification is `<saipen_home>/saipen/UI.md`.
`Vintage Golden` is the Golden Default.
Do not rename it to `Wintage Golden`, do not introduce another palette, and do not create a copied `VINTAGE_GOLDEN.md` inside the subSaipen.
A copied specification would become a second source of truth and drift.
`saiui` must load the canonical file by reference on every adoption.

DELIVERABLE A — BUILT-IN ROLE CHARTER
Create:

`extensions/subs/saiui.md`

The charter must define `saiui` as all of the following:
- senior product designer;
- interaction designer;
- UI systems designer;
- accessibility reviewer;
- UI-focused fixer/implementer;
- strict guardian of the canonical Vintage Golden specification.

The charter must explicitly bind `saiui` to the fixer contract in `extensions/subs/PROTOCOL.md § 9`:
- clone exact target files into `kitchen/pen/`;
- edit only the copies;
- verify against the repository's existing harness;
- emit a unified patch and evidence through `kitchen/OUTBOX.md`;
- never write to the main project tree;
- never enter BUILD, SHIP, CLEAN, or TRANSLATE as a subSaipen;
- never mark an unexecuted patch `ready`.

REQUIRED READ ORDER FOR SAIUI
On every adoption, `saiui` must read in this order:
1. its own `STATE.md`, `BOARD.md`, and LOG tail;
2. project-local `.saipen/extensions/subs/PROTOCOL.md`;
3. project-local `.saipen/extensions/subs/saiui.md`;
4. canonical `<saipen_home>/saipen/UI.md`;
5. the target project's actual UI implementation and UI tests;
6. only the public backend/API surfaces called by that UI;
7. README or screenshots last, as possibly stale evidence rather than executable truth.

If the role charter or canonical UI specification is unavailable, stop with a `blocked` OUTBOX entry naming the missing path. Do not improvise a visual system from memory.

SAIUI DESIGN METHOD
Pin this deterministic sequence in the charter:

1. TASK MAP
   Identify the user's real daily tasks, secondary tasks, rare tasks, destructive tasks, and recovery tasks.

2. ACTION/STATE MAP
   For every visible control record:
   - exact action;
   - scope;
   - preconditions;
   - enabled state;
   - disabled reason;
   - success evidence;
   - failure evidence;
   - keyboard route.

3. CAPABILITY GAP MAP
   Compare existing public capabilities with visible controls.
   Classify every gap as:
   - existing capability hidden by UI;
   - existing capability exposed ambiguously;
   - UI-only missing behavior;
   - missing Core/backend contract;
   - documentation drift;
   - rejected noise.

4. INFORMATION ARCHITECTURE
   Place daily actions on the main surface, secondary actions in a stable named region, and rare/destructive actions behind an explicit text-labelled control or dialog.

5. PATCH WAVE
   First expose already-existing capabilities and remove ambiguity.
   Only after that request new backend contracts.
   Never mix a safe UI-only patch with speculative backend redesign in one patch.

6. VERIFICATION
   Prove layout, keyboard reach, state visibility, destructive scope, unchanged backend semantics, and target-size behavior before marking the OUTBOX entry ready.

CONTROL HEURISTICS
The charter must include these rules:
- Add a control only when it exposes a real capability, removes repeated work, prevents a likely mistake, makes important state visible, or provides materially useful control.
- Never add controls merely to make the interface look advanced.
- One control has one stable action.
- The same action label always has the same outcome.
- A button must not silently change meaning because an input is empty, a row is selected, or a hidden mode changed.
- A keyboard shortcut must not be the only route to an important action.
- Important controls use text labels; icons may support recognition but never replace essential labels.
- Disabled controls remain visible and have a visible reason when the reason is not obvious.
- Destructive confirmations name the exact action, exact scope, exact object count, and whether pending/unsaved items are included.
- Destructive actions never receive default focus.
- Status changes remain visible until replaced or dismissed; no auto-vanishing evidence.
- No layout movement after first draw.
- No background UI mutation unless the user explicitly enabled it.
- No hover-only meaning.
- No hidden adaptive reordering of controls.
- Full keyboard reach and visible focus are mandatory.
- The interface must remain understandable in a screenshot and without relying on color alone.

CONTROL-TYPE RULES
- Boolean value: checkbox or explicit two-state control.
- Small mutually exclusive set: radio group or compact select.
- Exact bounded integer: spinbox/numeric field with units, legal range, and default.
- Continuous bounded value where relative adjustment matters: slider plus exact numeric field, units, legal range, keyboard control, and reset-to-default.
- Exact date/time: visible labelled date and time fields; no hidden timezone conversion.
- Free text: labelled input; placeholder is example only, never the label.
- A slider is forbidden when exact entry is the primary task or when the value has only a few meaningful steps.

BACKEND CAPABILITY GATE
`saiui` may wire a UI control only to an already-existing, tested public API.
It may add UI-local validation, presentation state, layout, labels, dialogs, keyboard bindings, and adapter glue that does not alter domain semantics.

If a useful control requires new persistence, queue semantics, scheduling, transport, worker behavior, rate-limit logic, or domain rules:
- do not fake it;
- do not implement it in UI code;
- write a standard OUTBOX finding with `status: ready` or `blocked` as evidence permits;
- describe the exact Core contract required in `details`;
- let Core create the normal `T-###` ticket during collect.

Do not invent custom OUTBOX fields such as `verdict` unless the current schema explicitly permits them.
Use the standard § 2 complete-package fields and the § 9 patch fields exactly as currently defined.
For a no-git target use `source_head: no-git`, never `N/A`.

DELIVERABLE B — DETERMINISTIC ROLE LOADING
Extend the SubSaipen extension so built-in role charters are first-class inherited material rather than folklore.

Use the existing `extensions/subs/saitest.md` file as precedent.
Define built-in role charters as project-shared files matching:

`extensions/subs/sai*.md`

Implement and document this behavior:

1. FIRST BOOTSTRAP / SPAWN
   In addition to PROTOCOL.md, README.md, crew.md, and TEMPLATE/, copy all built-in `sai*.md` role charters from `<saipen_home>/extensions/subs/` into project-local `.saipen/extensions/subs/`.

2. SYNC
   `saipen sub sync` refreshes those inherited role charters together with the other shared extension material.
   It must still never touch any live `.saipen/extensions/subs/<name>/STATE.md`, BOARD.md, LOG.md, or kitchen/ content.

3. ROLE ADOPTION
   After spawn and before executing the subSaipen's own `next_action`, bare `<subname>` adoption must load project-local `.saipen/extensions/subs/<subname>.md` when that charter exists.

4. STALE OLD PROJECT
   If a subSaipen exists but its built-in charter is missing locally while `<saipen_home>` contains one, do not silently run as a generic worker.
   Stop with the exact recovery instruction `run saipen sub sync`, then adopt again.

5. CUSTOM ROLE
   A custom `sai*` name with no built-in charter remains a valid generic SubSaipen governed only by PROTOCOL.md and its own BOARD.
   Do not fabricate a charter for it.

Update at minimum:
- `extensions/subs/PROTOCOL.md`;
- `extensions/subs/README.md`;
- `extensions/subs/crew.md` only where its role/adoption explanation is affected;
- any bootstrap/sync contract references and validation rules that enumerate the inherited copy set.

Add `saiui` to the shipped role documentation.
Do not add it to `.saipen/extensions/subs/MANIFEST.md` unless a live local instance is actually spawned.
A built-in role definition is not the same thing as an active project worker.

TICKET NAMESPACE
Add an explicit `UI-` namespace row for `saiui` in the SubSaipen ticket-prefix table.
Do not rely on the generic first-four-letters fallback for this built-in role.

DELIVERABLE C — SAIUI OUTBOX CONTRACT
The role charter must require patch entries to use the current standard complete-package plus fixer fields, including:
- status;
- summary;
- main_project_refs;
- critical;
- severity from the currently valid taxonomy;
- producer: saiui;
- source_head;
- coverage;
- payload;
- verified;
- instructions;
- base_head where the fixer contract requires it;
- unified diff in `patch`;
- details.

The `details` section must contain:
- user task and user cost;
- evidence from actual controls/functions/tests;
- hidden existing capabilities;
- ambiguous actions;
- missing state visibility;
- Vintage Golden violations by canonical rule;
- exact patch boundary;
- backend contracts deliberately not implemented;
- residual risk.

A UI redesign may be large when evidence justifies it, but the handoff must remain reviewable:
- separate mechanical visual-system normalization from behavioral UI changes when practical;
- separate existing-API exposure from new-API requests;
- never bury backend semantic changes inside a layout diff.

DELIVERABLE D — TARGET-PROJECT MISSION ARTIFACT
Create a non-canonical handoff artifact for the actual SAISENT repository:

`.saipen/kitchen/SAIUI_SAISENT_MISSION.md`

This file is not a second role charter and not a copy of UI.md.
It is a concrete mission the user can carry into the SAISENT project after `saiui` ships.

The mission must instruct the target worker to VERIFY, not assume, these seed hypotheses against current SAISENT code:
- one send control may change meaning between text-send and queue-send;
- existing queue operations may be hidden from the UI;
- bulk delete/clear-all may be absent;
- edit mode may lack visible Save/Cancel actions;
- exact date and time for one queued item may require a new Core contract;
- global/session scheduling may be confused with per-item scheduling;
- current layout may not satisfy the canonical 640x480 requirement;
- configuration values may deserve classified advanced controls, but not all values belong in the UI.

If a hypothesis is no longer true, mark it stale and do not manufacture work to satisfy the mission text.
Running code and tests outrank the mission.

The target mission must include this two-seat runbook:

Core seat:
1. `saipen sub sync`
2. `saipen sub spawn saiui` if not already present
3. write the concrete `UI-001` mission onto the subSaipen's own BOARD
4. remain the only main-tree writer

SAIUI seat:
1. run `saiui`
2. audit actual source and tests
3. clone allowed target files into `kitchen/pen/`
4. prepare and verify the patch
5. write a complete ready OUTBOX package
6. stop without touching the main tree

Core seat after handoff:
1. run `saipen collect saiui` for the complete package
2. re-check freshness and boundary
3. apply patch
4. run Core VERIFY -> REVIEW -> SHIP
5. create separate Core tickets for missing backend contracts

The target mission must explicitly forbid:
- direct main-tree edits by `saiui`;
- fake controls with no backend behavior;
- changing queue JSON/persistence/worker semantics in a UI patch;
- claiming manual or screenshot QA that was not performed;
- treating README claims as stronger than current code.

VALIDATION AND RED CONTROLS
Extend validation so this role cannot silently decay.
At minimum add checks and red controls for:

1. `extensions/subs/saiui.md` missing.
2. The charter no longer references canonical `saipen/UI.md`.
3. The charter contains a copied palette/token block or declares a second palette.
4. The main-tree write ban is softened.
5. The fixer pen/OUTBOX requirement is removed.
6. Role adoption no longer loads a present project-local charter.
7. First bootstrap omits built-in `sai*.md` charters.
8. `saipen sub sync` omits built-in charters or touches a live sub folder.
9. `saiui` is documented without an explicit `UI-` prefix.
10. A target mission claims SAISENT was audited from this repository.

Add a focused scenario fixture proving:
- bare `saiui` first-spawns/adopts normally;
- it loads PROTOCOL, its charter, and canonical UI.md before planning;
- it writes only inside its own folder;
- a patch leaves through OUTBOX;
- Core collect is the first main-project write;
- a missing backend API becomes a contract request rather than UI invention;
- a missing inherited charter in an old project produces the exact sync recovery path.

Use the repository's existing validation architecture rather than creating an unrelated test runner.

NON-GOALS
- Do not patch SAISENT from this repository.
- Do not spawn a live `saiui` instance in this SAIPEN repository merely to make the task look complete.
- Do not copy `saipen/UI.md` into the role or instance.
- Do not create a theme selector or alternate palette.
- Do not turn `saiui` into a generic frontend framework.
- Do not alter Core/backend semantics while implementing the role.
- Do not special-case one application inside the canonical role charter.
- Do not disturb unrelated tickets beyond the required checkpoint/pivot bookkeeping.

VERIFICATION GATE
Run the full existing repository gates appropriate to the host, including at minimum:
- `python tools/validate.py`;
- the portable validation floor;
- `python tools/audit_checks.py`;
- `python tools/run_scenarios.py`;
- any documentation/citation/parity checks affected by the changed files.

Record exact commands and results.
Do not report PASS for a skipped or timed-out gate.
If a slow existing gate is blocked by the current in-flight T-399 work, preserve the truthful dependency rather than fabricating completion.

DONE MEANS
DONE is not:
- a local empty `saiui/` folder;
- a copied UI specification;
- a prose-only role with no loader;
- a README mention;
- an unverified patch;
- a claim that SAISENT was improved.

DONE means all of the following are true:
- `saiui` is a shipped built-in role with a canonical charter;
- it loads the one authoritative `saipen/UI.md` rather than duplicating it;
- bootstrap, sync, and bare role-adopt handle built-in charters deterministically;
- `saiui` is a fixer-type read-only worker with full redesign authority only inside its pen;
- main-tree integration remains Core-only;
- the `UI-` namespace is documented and validated;
- complete OUTBOX patch semantics are defined without invented schema fields;
- red controls and a focused scenario protect the contract;
- the separate SAISENT target mission exists and labels its initial findings as hypotheses to verify;
- all applicable gates are truthfully green;
- current Core STATE, BOARD, and LOG preserve prior in-flight work and accurately record this objective.

Begin now.
```
