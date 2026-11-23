# T-1970 — how far SRC-351 can honestly get

SRC-351 is the FreeBuff wrong-protocol-routing audit (`audit/29.md`, sha256
`d72a8d2c…91afa9`) turned into a Work item. Its contract was a
**seeded-empty residue** — 0 clauses, 0 requirements — so the receipt could
never close no matter what anyone did (`SOURCE_UNRESOLVED` forever). That is the
same defect class `saipen/SOURCES.md` names at REQUEST-CLAUSE-01.

## What was built

Thirteen clauses, committed as immutable revisions 1..13 via
`saipen source req` (`.saipen/evidence/T-1970-audit/clause-plan.json`,
`clauses.tsv`). The deterministic deriver
(`saipen_engine/source_append.derive_normative_clauses`) yields only four units
from this body — the audit's own §11 handoff invariants — so the rest is agent
semantic extraction, which `SOURCES.md` says is the agent's job, not a parser's.

## Dispositions

| clause | disposition | basis |
|---|---|---|
| R001 | VERIFIED | `FOREIGN_PROTOCOL_COMMAND` names protocol + full invocation, not `unknown command` |
| R002 | VERIFIED | refusal carries `next_action` + `exact_namespace` declaration |
| R003 | VERIFIED | `cc` exit 0, `continue` exit 0, neither attributed foreign |
| R004 | VERIFIED | 3 damaged registry forms → `None`, no invented owner |
| R005 | VERIFIED | focused gate PASS ran 52, journal E-19596 |
| R012 | VERIFIED | live registry reports `ADVISORY`/`NONE`; the audit claims no more |
| R013 | VERIFIED | `operator_task.py` defines `model_supplied` as unverified origin and refuses promotion; 30 witness/ingress tests PASS |
| R006 | **BLOCKED** | needs the HOST to own namespaces before skill matching |
| R007 | **BLOCKED** | needs the HOST to stop treating `NO_HOME` as a directory hint |
| R008 | **BLOCKED** | needs the HOST to reload `~/.agents/skills/` at session start |
| R009 | **BLOCKED** | `INSTALLED_HOST` — the audit §8 already says BLOCKED |
| R010 | **BLOCKED** | `LIVE_END_TO_END` — no FreeBuff run exists, none can be simulated |
| R011 | **BLOCKED** | SAIPAL-side reconciliation; no authority over `.saipal/` |

7 terminal, 6 external. `saipen source close SRC-351` therefore returns
`SOURCE_UNRESOLVED` — **correctly**. `BLOCKED` is not terminal by design
(`intake.TERMINAL_DISPOSITIONS`), and `UNAVAILABLE_ENVIRONMENT` is unavailable
here because these clauses were not normalized in advance with a structured
`when_environment`, and the host is present, not absent.

## Why the seven are not fixable from here

`extensions/adapters/registry.json` declares this host
`declared_strength=ADVISORY`, `response_enforcement=ADVISORY`,
`pre_output_interception=NONE`. There is no interception surface. Any claim that
SAIPEN prevents the substitution would be false; the audit's §10 already refuses
that claim and this ticket does not contradict it.

## Deliverables

- `.saipen/evidence/T-1970-audit/FREEBUFF-ROUTING-HANDOFF.md` — the four host
  changes, the measured SAIPEN half, and the acceptance FreeBuff owes
  (`R006`-`R010`).
- `.saipen/evidence/T-1970-audit/SAIPAL-RECONCILIATION-REQUEST.md` —
  append-only reconciliation ask for the five `NO_DRIFT` receipts (`R011`),
  with an explicit list of what is *not* requested.
- `.saipen/evidence/T-1970-audit/SAIPAL-RECONCILIATION-REQUEST.md` records that
  SAIPAL's `NO_HOME` was correct behaviour, not a defect.

Both are **prepared locally, not sent**. Sending them is a separate decision.

## Raw measurements

`.saipen/evidence/T-1970-audit/`:
`refusal-separation.log`, `positive-controls.log`, `registry-and-skills.log`,
`host-and-bzrea-state.log`, `bzrea-host-entry.json`, `t1968-module-fresh.log`.
