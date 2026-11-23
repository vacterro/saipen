# FreeBuff wrong-protocol routing: receiving-owner handoff

Owner: T-1970 / SRC-351, derived from the audit
`audit/SAIHANDOFF_FREEBUFF_WRONG_ROUTE_BZ_REA_20261029.md` (sha256
`d72a8d2c…91afa9`, audit layer 29).
Receiving owner: FreeBuff Desktop skill/prompt dispatch and session inventory.
Status: **prepared locally, not sent.** Every clause below is `BLOCKED` in
SRC-351 coverage because it is host-side work this repository cannot perform.

This handoff covers **routing**, not provenance. The operator-origin gap is a
separate document under T-1819 / SRC-278
(`.saipen/evidence/T-1819-freebuff-route/FREEBUFF-IMPLEMENTATION-HANDOFF.md`)
and is not restated here.

## What SAIPEN measured, and what it changed

The incident: an agent told to run `/saipen continue` inside `_BZ_REA` loaded
SAIPAL, got `NO_HOME` from it, changed directory into the SAIPAL repository, and
worked there. SAIPEN's share of that defect was real and is repaired:

| SAIPEN-side fact | Measurement |
| --- | --- |
| Launcher available from `_BZ_REA` | `host entry` → `PATH_LAUNCHER`, `degraded: []`, `command_allowed: true` |
| SAIPEN skill installed correctly | `8efc2010…aef8fe` both sides (installed vs canonical) |
| Foreign command vs typo were byte-identical refusals | **the defect** — both `VALIDATION_FAILED: unknown command` |
| Now: foreign token is typed | `FOREIGN_PROTOCOL_COMMAND` naming `saipal`, full invocation, `next_action` |
| Now: typo still a typo | `bogusxyz` → `VALIDATION_FAILED: unknown command` |
| SAIPEN's own verbs unaffected | `cc` exit 0, `continue` exit 0 |
| Damaged registry invents no owner | block deleted / non-dict / bad protocols → `None` |

Authority for that repair is `saipen/REGISTRY.json` → `exact_namespace`
(rule `EXACT-NAMESPACE-01`), resolved by
`tools/saipen_engine/commands.py::foreign_protocol_owner`.

## What FreeBuff must change

Four items, each answering one `BLOCKED` clause of SRC-351.

1. **Exact namespace ownership before semantic skill matching** (`SRC-351:R006`).
   An explicit `/saipen <cmd>` must never be dispatched to a skill whose name
   merely resembles it. Decide the namespace first, then look up a skill.
2. **Never present SAIPAL as a candidate for an explicit SAIPEN command**
   (`SRC-351:R002`-adjacent host half). `~/.agents/skills/saipal/SKILL.md`
   advertises `continue, next, submit, report, status` — the same verbs SAIPEN
   owns. Offering it for `/saipen …` is the observed failure.
3. **A protocol refusal must not cue a working-directory change**
   (`SRC-351:R007`). `NO_HOME` from a foreign protocol means "wrong protocol",
   not "wrong directory". SAIPEN now states this in its own refusal
   (`no_home_substitution`), but the host is what moved.
4. **Re-read `~/.agents/skills/` on session start** (`SRC-351:R008`) so a stale
   inventory cannot map a namespace to the wrong owner.

## Why SAIPEN cannot close items 1-4 itself

The live adapter registry declares this host:

```
id=freebuff  declared_strength=ADVISORY  response_enforcement=ADVISORY
pre_output_interception=NONE
```

There is no pre-render interception surface, so no SAIPEN-side change can
constrain what the host's skill picker offers a model. Claiming otherwise would
be exactly the "native prevention where only prompt steering exists" failure the
audit's own §10 refuses.

## Acceptance the receiving owner owes

- `SRC-351:R009` — the host stops offering a substitute for an explicit command.
- `SRC-351:R010` — a live `/saipen continue` in
  `V:/___VAC/__K/__CODE/_MISC/_BZ_REA` runs the SAIPEN route end to end.

Both are `INSTALLED_HOST` / `LIVE_END_TO_END`. The SAIPEN half of R010 is already
proven from the affected project (`.saipen/evidence/T-1970-audit/bzrea-host-entry.json`);
what is missing is a real FreeBuff run, which no test in this repository can
supply.

## Not claimed

- No native prevention. Only the typed refusal and the registry declaration.
- No SAIPAL modification or disablement. A deliberate, explicit SAIPAL request
  remains legal (`exact_namespace.foreign_protocols.saipal.legitimate_use`).
- No operator-origin upgrade: SRC-351's meta records
  `request_provenance.witness = model_supplied` and this handoff does not change
  that. See T-1819 for the native chain.
