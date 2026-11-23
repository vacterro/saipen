# RAPORT — SAIPEN: `finish` routes into a gate-refused verb and the refusal names no route

- **Report id:** RAPORT-SAIPEN-ROUTELESS-FINISH-20260918
- **Date:** 2026-09-18
- **Reporter:** agent `opencode` (SAIPEN seat inherited from project STATE), host opencode (`SAIFREN`)
- **Reporter project:** `V:\___VAC\__K\__CODE\_PY\_LIMISAW`
- **Project lineage:** `lineage-a41c0e3a81534f02a4cc4520a399cca6`
- **Protocol version:** 8.0.1
- **Observed runtime home:** `C:\Users\vac34\.config\opencode\skills\saipen`
- **Bound saipen_home (project):** `C:\Users\vac34\AppData\Local\saipen\scheduled-source`
- **Protocol home (source):** `V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN`
- **Defect class:** routing / refusal-without-route (`PROTOCOL_VIOLATION`)
- **Severity:** P2
- **Origin:** improve cycle `imp-vacterro-limisaw-20260918-1` RUN-1/IMP-001 (CONFIRMED -> ticket T-53)

## 0. TL;DR

The deterministic router emits an action the protocol's own gate refuses, and the
refusal carries no route to the move that would actually work:

1. With a DOING umbrella ticket (`T-52`) whose linked receipt (`SRC-011`) still
   has non-terminal actionable clauses, `saipen continue --json` returned
   `action: "PHASE BUILD T-52"`, `reason: "finish"`.
2. The BUILD phase's only finish verb, `saipen ticket done T-52`, refused
   `SOURCE_UNRESOLVED` listing the unresolved clauses — with **no
   `next`/`next_action`/`canonical_next_command` field**.
3. The reachable forward move (`saipen ticket block T-52 ...`) was therefore
   never named; the agent that follows the router spins.

This is the `SRC-053` trigger class: an engine-emitted refusal with no legal
forward route.

## 1. Deterministic reproduction

Preconditions: a bound project where one `## DOING` ticket is the umbrella for a
source whose coverage is not yet fully terminal.

```
saipen continue --json
 -> {"ok":true,"action":"PHASE BUILD T-52","ticket":"T-52","reason":"finish"}

saipen ticket done T-52 --json
 -> {"ok":false,"code":"SOURCE_UNRESOLVED", ...,
     "unresolved":["SRC-011:R002",...,"SRC-011:R014"]}
    (no next / next_action / route field)
```

The only route that advances the state is `saipen ticket block T-52 "<reason>"`,
which was executed and committed (BLOCK, E-438) — proving the route exists and
was reachable, but the engine never named it.

## 2. Root cause

- `tools/saipen_engine/intake.py:1905` `work_closure_gate` returns
  `SOURCE_UNRESOLVED` while any linked actionable clause is non-terminal
  (intake.py:1962-1970).
- `tools/saipen_engine/operations.py:2859-2865` — the `finish_ticket` path
  returns that refusal (`_refuse(source_gate.get("code", ...), ...)`) with
  `receipt` and `unresolved` only; it sets no `canonical_next_command`. By
  contrast the sibling branches at operations.py:2851 carry an explicit
  `canonical_next_command=_evidence_route(...)`.
- The router routes `finish` for a DOING ticket (routed `PHASE BUILD T-52`,
  reason `finish`) without checking that the work-closure gate is green, so it
  can emit an action its own finish verb refuses.

## 3. Impact

- A session that trusts `continue`'s action runs a verb the gate refuses, gets
  no route, and must independently discover `ticket block` — the exact
  "refusal with no forward route" class `admission.py::_BRAKE_ROUTES` closes for
  protocol-state refusals but not for the source-coverage refusal.
- Recurrence across projects is plausible wherever one umbrella Work carries a
  multi-clause audit/imported source (the normal audit-inbox shape).

## 4. Suspected owner

- `tools/saipen_engine/operations.py` — `finish_ticket` SOURCE_UNRESOLVED branch
  (add the reachable `canonical_next_command`, e.g. the `ticket block` route).
- `tools/saipen_engine/router.py` — do not route `finish` into an action whose
  source-coverage gate is red; name the reachable command instead.

## 5. Repair candidates

1. In the `SOURCE_UNRESOLVED` branch of `finish_ticket`, carry a
   `canonical_next_command` naming the reachable move (`ticket block <T-###>
   <reason>` for a ticket whose source cannot close; `source disp ...` for one
   that can).
2. Have the router consult `work_closure_gate` before emitting `finish`, so an
   action the gate will refuse is never surfaced as the next step.
3. Distinguish "coverage incomplete but a route exists" (name it) from
   "coverage incomplete and the route is an operator decision" (WAIT_USER with
   proof).

## 6. Related

- `SAI-DEFECT-20260918-ingress-shell-operator-as-request`,
  `SAI-DEFECT-20260918-guard-readonly-probe-gap`,
  `SAI-DEFECT-20260918-saipenview-guard-restart`,
  `SAI-DEFECT-20260917-wintage-guard-filepath` (protocol_incidents/inbox) —
  independent mechanisms, same "refusal / classification with no usable route"
  family.
- `audit/18.md`, `audit/19.md` (home `.saipen/evidence/`) — refusal-without-route
  family in the SAIPEN project's own inbox.

## 7. Side effects disclosed

- `saipen ticket block T-52` was executed (BLOCK, E-438) — the reachable move the
  refusal failed to name.
- The improve cycle `imp-vacterro-limisaw-20260918-1` was completed; IMP-001 was
  disposed CONFIRMED -> T-53. No canonical file was hand-edited.

— end of report —
