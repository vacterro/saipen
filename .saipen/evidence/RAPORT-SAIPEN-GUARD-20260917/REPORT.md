# RAPORT — SAIPEN guard malfunction + how to report it to the SAIPEN protocolist

- **Report id:** RAPORT-SAIPEN-GUARD-20260917
- **Date:** 2026-09-17
- **Reporter:** agent `antigravity` (SAIPEN seat inherited from project STATE), host opencode
- **Reporter project:** `V:\___VAC\__K\__CODE\_TAMPERMONKEY\_WIN95THEME\Wintage`
- **Project lineage:** `lineage-30ee844c69d34eb68605a4563cfdb8ff`
- **SAIPEN home (protocol):** `V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN`
- **Installed runtime:** `C:\Users\vac34\.config\opencode\skills\saipen`
- **Protocol version (both):** 8.0.1 -- **but they are DIFFERENT installs** (`RUNTIME_DRIFT`)
- **Guard plugin:** `C:\Users\vac34\.config\opencode\plugins\saipen-guard.js` (build `T-1327-zero-manual-recovery-20260914.1`)
- **Defect classes in this report:** 3 (guard/engine misclassification, transport dead-end, runtime drift)

## 0. TL;DR

Three independently reproduced defects, all in the guard/engine boundary, not in any
project:

1. **A canonical `saipen start --file <Windows-path>` is classified as an ordinary
   SHELL effect** because Windows paths use `\`, a character the guard's own
   shell-syntax detector claims. Consequence: on a project with no active DOING Work
   the guard refuses it `NO_ACTIVE_WORK`, while the identical command with `/`
   separators is admitted. **The guard's own advertised recovery command is
   unreachable in the exact state it was emitted for.**
2. **`INGRESS_TRANSPORT_UNSAFE` names `saipen start --file <path>` as the route, then
   that route is refused** -- a self-referential loop.
3. `saipen defects` exists conceptually (registered as `SRC-053`) but is not
   implemented, so there is **no canonical protocol-incident inbox**; reports still
   land in ad-hoc paths.

There is **no user-facing `saipen defect(s) emit` command** in this runtime. Until
`SRC-053` ships, the canonical reporting route is a RAPORT under the SAIPEN home
evidence tree plus the project's Improve lifecycle; details in §4.

---

## 1. Defect A -- backslash path drops the canonical-operation exemption

### Reproduction (all commands read-only except the `start` probes)

Project state: `phase: DONE`, `task: none`, no `## DOING` Work.

```
# 1. canonical, forward-slash path -> runs (engine answers)
saipen start --file V:/_TEMP_/opencode/guard-probe.txt
    -> REFUSE [VALIDATION_FAILED] --file ... is not a readable UTF-8 file   (engine ran)

# 2. once the file exists, same command -> runs
saipen start --file V:/_TEMP_/opencode/guard-probe.txt
    -> action: PHASE SCOUT T-259 ... code: STARTED                          (engine ran)

# 3. SAME command, backslash path -> REFUSED BY THE GUARD, never reached the engine
saipen start --file V:\_TEMP_\opencode\guard-probe.txt
    -> SAIPEN_GUARD_REFUSAL: NO_ACTIVE_WORK: the saipen guard refused tool 'bash'
```

The forward-slash and backslash forms of one command are answered two different
ways. That is precisely the "one question, two answers" class the engine's own
comments say T-1354/T-1363 closed.

### Root cause (exact sources)

`tools/saipen_engine/guard_events.py:184`

```python
_SHELL_SYNTAX_CHARS = frozenset("|&;<>(){}[]$`*?~!\\\"'#\n\r\t")
```

`\` is a member. `tools/saipen_engine/guard_events.py:1043` (`_saipen_cli_tokens`):

```python
if any(char in _SHELL_SYNTAX_CHARS for char in command):
    return _ingress_payload_tokens(command)
```

A `saipen start --file V:\...` line therefore abandons the canonical grammar and
falls through to the ingress-payload parser. `_ingress_payload_tokens`
(`guard_events.py:976`) returns `None` because there is no quoted payload, so
`_saipen_cli_verb` returns `None` (`guard_events.py:1063`), and `map_event`
classifies the line as `action = "shell"` (`guard_events.py:1251-1252`). Ordinary
shell effects then pay the protocol-state brake in `admission.evaluate_admission`
and are refused `NO_ACTIVE_WORK` (`admission.py:758-763`) when no `## DOING`
Work exists -- exactly the state in which the model is told to use `--file`.

The forward-slash form survives because `/`, `:`, `_`, `.`, `-` are all inside
`_SAIPEN_ARG_CHARS` (`guard_events.py:189-191`) and none are in
`_SHELL_SYNTAX_CHARS`.

### Why this matters

`\` is the **native Windows path separator**. On this host the guard's canonical
transport is therefore unreliable for every Windows absolute path, including the
one the guard itself prints (Defect B).

### Candidate fix (engine side; maintainer decides)

- Treat `--file`/`--hex` value tokens as opaque path arguments in
  `_saipen_cli_tokens`, OR exempt `\` from `_SHELL_SYNTAX_CHARS` when it appears
  inside a token that is not a shell metacharacter in the active host
  (PowerShell does not use `\` as an escape), OR
- accept the backslash spelling explicitly in the canonical grammar's argument
  alphabet for path-valued options.

Do **not** "fix" this by telling agents to use forward slashes: the guard emitted
the backslash form.

---

## 2. Defect B -- the transport route refuses its own replacement

Reproduced earlier in this session on the Wintage project (DONE, no DOING work):

```
saipen user-request "<long prose payload>"
    -> SAIPEN_GUARD_REFUSAL: INGRESS_TRANSPORT_UNSAFE:
       the request text cannot survive one quoted shell argument unchanged;
       run the command in canonical_next_command instead.
       ... then run that command with the file's project-relative path
       next: saipen start --file <path>
```

Running the named route (`saipen start --file <path>`) with a Windows backslash
path is then refused by Defect A (`NO_ACTIVE_WORK`). The guard emits a route it
will not admit, and the model enters a refusal carousel with no legal forward
route -- the trigger condition `SRC-053` §"WHEN AN AGENT MAY EMIT A REPORT"
names verbatim ("guard blocks the only engine-required repair path").

Sources: `guard_events.py:948-973` (`ingress_rewrite`),
`guard_events.py:1380-1399` (`INGRESS_TRANSPORT_UNSAFE` + instruction).

---

## 3. Defect C -- no canonical incident channel (`saipen defects` absent)

```
saipen defects list --json
    -> {"ok": false, "code": "RUNTIME_DRIFT",
        "detail": "command 'defects' is not implemented by this runtime, and this
                   project's saipen_home points at a DIFFERENT SAIPEN install"}
```

```
Test-Path "$env:LOCALAPPDATA\saipen\protocol_incidents"   -> False
```

The **registered** requirement is `.saipen/intake/active/SRC-053.md`:

> CENTRAL PROTOCOL INCIDENT INBOX / FIRST-CLASS SAI-DEFECT ROUTING
> `%LOCALAPPDATA%\saipen\protocol_incidents\` — ONE OWNER, ONE ROOT, ONE FORMAT,
> ONE DISCOVERY COMMAND; header `SAI-DEFECT!1`; `saipen defect emit
> --from-current-failure`; read-only protocolist discovery; claim without
> mutating the blocked project; 12 acceptance cases.

It is captured, linked as `SRC-053`, and explicitly NOT implemented ("REGISTER
ONLY during the current T-1370/T-1367 corridor"). So the inbox does not exist in
8.0.1 and no `saipen defects` verb is registered (`saipen --help` output confirms).

Additionally the runtime reports:

```
"distribution": {
  "installed": 6, "stale": 4, "unknown": 1, "fresh": false,
  "blocked": "DIRTY_SOURCE",
  "blocking_paths": ["M tools/saipen_engine/audit_manifest.py",
                     "M tools/test_audit_manifest.py"],
  "summary": "4 of 6 home(s) stale -- newest installed head e7ab966fe4f2 ..."
}
```

and the project's own `saipen status` reports
`RUNTIME_DRIFT (project saipen_home V:\...\_SAIPEN vs executing runtime C:\...\skills\saipen)`.
A defect report must therefore name the **generation** it was observed on (§5).

---

## 4. HOW TO REPORT THIS TO THE SAIPEN PROTOCOLIST / MAINTAINER

There are four channels. Use them in this order.

### 4.1 The registered-but-unimplemented canonical channel (`SRC-053`) -- PREFERRED once it ships

`.saipen/intake/active/SRC-053.md` defines the intended mechanism:

- storage: `%LOCALAPPDATA%\saipen\protocol_incidents\{inbox,claimed,resolved,invalid,evidence}`
- packet header: `SAI-DEFECT!1` with `incident_id`, `created_at`,
  `reporter_project`, `reporter_identity`, `protocol_version`,
  `runtime_generation`, `installed_home`, `defect_class`, `severity`, `state`,
  `blocker`, `canonical_next_command`, `evidence_digest`, `dedupe_key`,
  `source_report_path`
- emit: conceptually `saipen defect emit --from-current-failure`
- discovery: `saipen defects` / `saipen defects show <id>`
- claim lifecycle: `INBOX -> CLAIMED -> RESOLVED` (or `-> INVALID`), and
  **claiming must not mutate the blocked project**

Until it exists, mirror its shape by hand (see §5) so the eventual import is a
one-to-one migration. `SRC-053` §"MIGRATION / EXISTING REPORTS" says to import
only reports provably genuine, preserving original path/provenance.

### 4.2 The repository's official contribution routes

From the SAIPEN home's own docs (these ARE the canonical "report to the
protocolist" instructions shipped in the repo):

- `CONTRIBUTING.md` §"Reporting a gap": open an issue naming the file/section,
  the concrete evidence (quote, command + actual output, minimal reproduction),
  and the expected behaviour. Vague reports are explicitly declined.
- `.github/ISSUE_TEMPLATE/bug_report.md`: the template. Required sections
  **Where**, **Evidence**, **Expected**, **Checked first** (whether
  `CHANGELOG.md` / `.saipen/KNOWLEDGE/decisions.md` already decided otherwise).
- `SECURITY.md` §"Reporting a Vulnerability": only for a real, currently
  exploitable bootstrap/secret-hygiene problem, via the repo's **Security** tab
  ("Report a vulnerability"), not a public issue. Guard misclassification is a
  protocol gap, **not** a security advisory -- use the bug template.
- `CONTRIBUTING.md` §"Before proposing a change": the three-question SAIPEN
  Litmus Test (`SPEC.md`); a fix proposal should name which question it improves.
- Repo remote: `https://github.com/vacterro/saipen.git` (from
  `.git/config`) -- issues go to `vacterro/saipen`.

### 4.3 The in-project Improve lifecycle (protocol meta-control)

`saipen/IMPROVE.md` owns a read-only audit lifecycle whose seat report can carry a
finding against the protocol itself. This session already has an active cycle:

```
saipen improve            -> IMPROVE_AUDIT_ASSIGNMENT
   cycle_id: imp-vacterro-wintage-20260916-4
   seat_id:  antigravity-01
   report:   .saipen/improve/imp-vacterro-wintage-20260916-4/antigravity-01/saipen_improve_SAIPEN.md
   next:     saipen improve submit imp-vacterro-wintage-20260916-4 antigravity-01 SAIPEN <findings.json>
```

A finding is `IMP-###` inside a `## RUN N`, header carrying
`severity: P0|P1|P2|P3`, and identity
`<cycle>/<seat>/<report>#RUN-N/IMP-NNN` (IMPROVE.md §6). Submit mechanically with
`saipen improve submit`; complete with `saipen improve complete`; Core judges via
`saipen improve sweep`. This is the **in-project** evidence path -- it does not
require the protocolist to know a temp path, but it is per-project, which is
exactly the discoverability gap `SRC-053` exists to close.

### 4.4 The SAIPAL analyst seat (protocol-drift observer)

The `saipal` skill (`SKILL.md`) is the Layer-B analyst for SAIPEN-governed
sessions: read real session evidence, decide whether observed behaviour
contradicted the governing protocol version, submit structured drift candidates,
and report to the operator. Trigger: `saipal report` / `saipal cc`. Precedent in
the home: `.saipen/evidence/SAIPAL-deadlock-state-history-binding-20260916/REPORT.md`.
Use this when the finding is "the protocol's stated contract and the runtime's
behaviour disagree", which is exactly Defects A and B.

### 4.5 Do NOT

- Do **not** write the report only into `V:\_TEMP_\...`, `future_gate/`, or any
  other ad-hoc path -- `SRC-053` names this as the discoverability failure.
- Do **not** edit `.saipen/STATE.md`/`BOARD.md`/`LOG.md` by hand to record it;
  those are protected canonical namespaces.
- Do **not** use `future_gate/` as the raw spool; it is post-triage follow-up,
  not the incident inbox (`SRC-053` §"FUTURE_GATE RELATIONSHIP").
- Do **not** fabricate a ticket or edit an unrelated project's production code to
  "fix" a protocol defect.

---

## 5. Incident packet for THIS report (ready to import)

Following the `SRC-053` `SAI-DEFECT!1` header shape, since `saipen defect emit`
does not exist yet:

```
SAI-DEFECT!1
incident_id:            SAI-DEFECT-20260917-wintage-guard-filepath
created_at:             2026-09-17T00:00:00Z
reporter_project:       V:\___VAC\__K\__CODE\_TAMPERMONKEY\_WIN95THEME\Wintage
reporter_identity:      antigravity
protocol_version:       8.0.1
runtime_generation:     installed C:\Users\vac34\.config\opencode\skills\saipen
                        (head e7ab966fe4f2 per distribution report; 4 of 6 homes stale)
installed_home:         C:\Users\vac34\.config\opencode\skills\saipen
protocol_home:          V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN
defect_class:           guard-canonical-classification / ingress-transport-deadend
severity:               P1
state:                  INBOX
blocker:                a canonical saipen start --file <Windows path> is refused
                        NO_ACTIVE_WORK when no DOING Work exists; the guard's own
                        advertised replacement route is therefore unusable
canonical_next_command: (none -- this is the defect)
evidence_digest:        sha256 of this REPORT.md
dedupe_key:             guard/backslash-path-drops-canonical-exemption/8.0.1
source_report_path:     V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN\
                        .saipen\evidence\RAPORT-SAIPEN-GUARD-20260917\REPORT.md
```

### Deterministic reproduction (for the packet body)

Ground facts: `guard_events.py:184` includes `\` in `_SHELL_SYNTAX_CHARS`;
`guard_events.py:1043` abandons the canonical parse on any such char;
`_ingress_payload_tokens` returns `None` without a quoted payload;
`admission.py:758` refuses ordinary shell effects without exactly one DOING Work;
`_SAIPEN_ARG_CHARS` (`guard_events.py:189`) contains `/` but `_SHELL_SYNTAX_CHARS`
contains `\`.

Observed matrix (project `phase: DONE`, no `## DOING`):

| command | classification | result |
|---|---|---|
| `saipen status --json` | saipen_op | admitted, ran |
| `saipen validate --json` | saipen_op | admitted, ran |
| `saipen start --file V:/_TEMP_/x.txt` | saipen_op | admitted, engine ran |
| `saipen start --file V:\_TEMP_\x.txt` | **shell** | **guard refused NO_ACTIVE_WORK** |
| `saipen status --project-root .saipen/missing` | saipen_op | admitted, engine ran |
| `saipen status --project-root .saipen\missing` | **shell** | **guard refused PROTECTED_CANONICAL_NAMESPACE** |

The last pair is a second, independent instance proving the rule is the
separator, not the specific verb. Both backslash forms fail; both slash forms
run. That is the minimal reproduction.

### Impact

- The guard's advertised recovery transport is unreachable in its own target
  state; a bound agent is left with no legal forward route (a carousel).
- Any Windows agent following the guard's `INGRESS_TRANSPORT_UNSAFE` instruction
  hits it.
- Discoverability is zero: no `saipen defects`, so this report has no canonical
  home (`SRC-053` unimplemented).

### Suspected owner

`tools/saipen_engine/guard_events.py` (`_SHELL_SYNTAX_CHARS`,
`_saipen_cli_tokens`, `_ingress_payload_tokens`) and, for the dead-end, the
interaction with `saipen_engine/admission.py::protocol_snapshot`.

### Repair candidates

1. Path-valued option values (`--file`, `--hex`, `--project-root`, `--runtime-info`)
   bypass `_SHELL_SYNTAX_CHARS` classification.
2. Treat `\` as a non-metacharacter on hosts whose shell does not use it
   (PowerShell/cmd); keep it for POSIX.
3. Implement `SRC-053` so this class has a first-class route regardless.

---

## 6. Side effects disclosed (this session)

- `saipen start --file V:/_TEMP_/opencode/guard-probe.txt` (forward-slash probe)
  **created a real ticket T-259** (SRC-015, `## DOING`, owner `antigravity`) and
  captured SRC-015. It is an artifact of the probe, not intended work. It should
  be retired or blocked by the operator with the canonical command
  (`saipen ticket retire T-259 --reason ... --evidence ... --authority ...`).
- `saipen improve` admitted a real cycle `imp-vacterro-wintage-20260916-4`
  (seat `antigravity-01`, draft report created, read-only).
- A scratch file `V:\_TEMP_\opencode\guard-probe.txt` was created outside every
  project tree. Cleanup was refused by the guard (`NO_ACTIVE_WORK`).
- No canonical project file was hand-edited. No event was fabricated.
- One earlier report remains in the home:
  `.saipen/evidence/RAPORT-WINTAGE-R015-20260917/REPORT.md`.

## 7. Relationship to the other parked Wintage blocker

Wintage also carries the protocol-wide unregistered-refusal-code defect logged at
E-1041 (`intake.work_closure_gate` returns `SOURCE_RECEIPT_MISSING`, a code
outside `REGISTRY.json['error_codes']`, and `ticket done` ends in a raw
`ValueError`). That is the **same family** as Defect C: a refusal code with no
registered route. Both are engine-side and both should ride one protocolist
review.

— end of report —

## Appendix — index of evidence

| Item | Path |
|---|---|
| This report | `V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN\.saipen\evidence\RAPORT-SAIPEN-GUARD-20260917\REPORT.md` |
| Prior RAPORT | `...\.saipen\evidence\RAPORT-WINTAGE-R015-20260917\REPORT.md` |
| SAIPAL precedent | `...\.saipen\evidence\SAIPAL-deadlock-state-history-binding-20260916\REPORT.md` |
| Incident-inbox requirement | `...\.saipen\intake\active\SRC-053.md` |
| Guard adapter | `C:\Users\vac34\.config\opencode\plugins\saipen-guard.js` |
| Engine (observed) | `C:\Users\vac34\.config\opencode\skills\saipen\tools\saipen_engine\{guard_events.py,admission.py}` |
| Repo contribution rules | `<home>\CONTRIBUTING.md`, `<home>\.github\ISSUE_TEMPLATE\bug_report.md`, `<home>\SECURITY.md` |
| Improve lifecycle | `<home>\saipen\IMPROVE.md` |
| Improvement cycle (live) | `<wintage>\.saipen\improve\imp-vacterro-wintage-20260916-4\` |
