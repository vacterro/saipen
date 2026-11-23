# SAIPEN — logical roadmap from the MCP / Cloud idea thread

STATUS: PLANNING ONLY. Not execution authority. Current STATE, BOARD, source
receipts and their verified evidence outrank this document. It neither reorders
BOARD nor authorizes publication, and it is not converted directly into Work:
when a stage becomes timely, one bounded slice becomes ONE FUTURE GATE with the
fields required by the
[adoption rules](SAIPEN_FUTURE_ARCHITECTURE_20260918/future_architecture/16_ADOPTION_RULES.md).

Derived 2026-09-29 from [SAIPEN_FUTURE_IDEA1.md](SAIPEN_FUTURE_IDEA1.md), which
is a chat transcript, not a specification, and is left untouched. Facts about
this repository were re-checked the same day; every percentage and revenue
figure in the source is an estimate and is kept here only as a hypothesis to
measure.

## 1. The source, reduced

Three connected arguments:

- **Critique.** Nine weaknesses (Python dependency, no distributed consensus,
  stochastic LLM, no fsync durability promise, discipline instead of
  mechanics, secrets in logs, overhead for tiny projects, injector side
  effects, not a Git replacement). A second opinion in the same thread rates it
  roughly 70-75% current, says half are deliberate documented boundaries, and
  names the real residual risks: stronger secret-leak prevention, degraded
  operation without Python, an explicit crash-durability model with tests, and
  a lightweight profile for small projects as product work.
- **MCP.** A façade over the existing engine, never a replacement: files stay
  the memory, the engine stays the authority, MCP is the universal socket.
  Local stdio first, richer payloads second, remote transport only if
  multi-agent demand is real.
- **Cloud.** Keep the protocol open source; sell only what the local version
  deliberately does not do (hosted registry, coordination, backup, dashboards).
  Local-first is a selling point. The first milestone is a paying user, not a
  server.

## 2. Invariants every stage must keep

| # | Invariant | How it is tested |
|---|---|---|
| I1 | Files are memory: with MCP and Cloud absent, `saipen continue` behaves exactly as today. | Parity run with the new surface disabled. |
| I2 | The engine (SAIOPS) is the only writer authority. A new surface calls it and never writes `.saipen/`. | Guard test: a surface that writes directly goes red. |
| I3 | Additive and optional: no stage makes a network, a daemon or an account mandatory. | Cold start with the network off. |
| I4 | A tool is not a permission. Exposing a verb does not authorize it; ship, push, clean, goal and Git effects stay operator-gated. | Effect-class mapping from `COMMAND_EFFECTS.json`. |
| I5 | Transport the protocol, do not replace it. Phases, evidence and acceptance are not collapsed into a few RPC verbs. | A surface may not skip VERIFY or REVIEW. |
| I6 | Each stage names the defect class it removes (CORE 1.1) and is measured, not estimated. | Red control before green. |
| I7 | One bounded FUTURE GATE at a time. | Adoption rules 1-3. |

## 3. Baseline today — do not restart completed work

| Claim in the source | State on 2026-09-29 | Consequence |
|---|---|---|
| Correctness rests on agent discipline. | Outdated. Mutations go through the engine with lock, journal and recovery. The final-response gate is MECHANICAL for OpenCode and Codex, and for Claude Code as of T-1558 (built, not yet installed). | Do not re-plan write-path safety. |
| Secrets in logs. | Partly covered: `codec.redact_credentials` redacts at the persistence boundary, by pattern only. No entropy scan, no pre-commit gate. | Real gap: Stage 1a. |
| Python is required. | Partly true. A frozen shell floor (`tests/validate.sh`, `validate.ps1`) exists; what it may still promise is not defined. | Real gap: Stage 1b. |
| No durability promise. | `fsync` exists in `codec.py` and `paths.py`; there is no written per-operation power-loss contract and no kill-point tests. | Real gap: Stage 1c. |
| Heavy for tiny projects. | No lightweight profile exists. | Product gap: Stage 1d. |
| MCP server. | None. `mcp` appears only as a runtime capability name in `RUNTIME.md`. Engine `--json` outputs (`status`, `continue`, `context orient`, `response style`) are the natural payloads. | Greenfield: Stage 2. |
| Multi-agent, multi-machine. | Designed, not built: `future_architecture/` (registry, lease broker, eligibility, dispatch). | Stage 4 sits on it, not beside it. |
| (not in the source) Hosts see the protocol as built. | No. The installed skill copies are stale (7 of 7 homes) because the injector refuses to publish a dirty source tree. | Stage 0. |

## 4. Logical order

    S0 converge the current line
     |
     +-- S1a secrets   S1b no-Python   S1c durability   S1d lite     (independent)
     |
    S2 MCP v1: local stdio, read-only first, writes only through the engine
     |
    S3 MCP v2: one structured continuation payload, capability negotiation
     |
    S4 multi-host gate: registry -> lease broker -> one serialization point -> remote
     |
    S5 Cloud: first paying user before any server

The order follows dependency, not appeal. S2 needs a converged, trustworthy
baseline (S0) and is more useful once the residual risks it would expose are
closed (S1). S4 needs measured multi-agent demand and a threat model. S5 needs a
buyer. Later stages may be dropped without invalidating earlier ones; earlier
stages may not be skipped to reach later ones.

## 5. Stages

### S0 — Converge what is already built

- **Defect class:** the protocol as hosts read it differs from the protocol the
  engine enforces.
- **Person no longer has to:** discover by accident that an agent runs on old
  rules. **Agent no longer has to guess** which copy of EXECUTION.md is real.
- **Work:** (1) resolve the dirty-tree deadlock so the injector can publish;
  (2) host proof and install for the response gates (T-1551 Codex trust, T-1558
  Claude hook); (3) remove operator hooks that carry their own voice or
  language rule (`style_hook_conflicts`) and the `cmd.exe /c` payload-executing
  hooks (`HOST_HOOK_RUNS_PAYLOAD`); (4) live-host acceptance per host.
- **Exit:** `saipen status --json` reports distribution fresh, adapters report
  MECHANICAL only where installed and current, `saipen validate` PASS.
- **Stop condition:** nothing beyond S0 starts while distribution reports
  `DIRTY_SOURCE`.

### S1 — Residual-risk hardening

Four independent gates, ordered by return. None of them touches a documented
boundary: distributed consensus, Git replacement and LLM correctness stay out of
scope, because fixing them would turn a continuation protocol into infrastructure.

| Gate | Defect class | RED control | GREEN acceptance | Non-goal |
|---|---|---|---|---|
| S1a secret-leak prevention | A secret that no pattern recognises reaches LOG, BOARD, STATE and then Git history. | A token shaped like a business identifier that the pattern set misses. | Pre-checkpoint and pre-commit scan (entropy, key shape, operator denylist) refuses with a finite remediation. | Proving no secret exists. |
| S1b degraded operation without Python | A host without Python loses all machine enforcement silently. | Cold `continue` with Python removed from PATH. | A named DEGRADED level: read-only orientation and floor validation work, mutation is refused with a stated reason, `status` reports the level. | Porting the engine to another language. |
| S1c crash-durability model | An unstated power-loss window. | Kill between the LOG and BOARD writes of one checkpoint. | A written per-operation durability contract and kill-point tests: recovery reaches a valid state or names the exact repair. | A universal durability guarantee. |
| S1d lightweight profile | Overhead exceeds value for a small project, so nothing continues there. | A 100-line-script fixture that must finish one ticket. | A lite mode (STATE, BOARD, LOG and a validator subset) with a lossless upgrade to full. | A second protocol. |

### S2 — MCP v1: local stdio façade

- **Defect class:** every host re-learns the protocol from Markdown and a CLI it
  may invoke wrongly; cold-start context is spent reading files.
- **Person no longer has to:** re-explain SAIPEN per host. **Agent no longer
  has to:** guess the root, the transport or the next command.
- **Prerequisites:** S0; engine JSON for `status`, `next`, `continue`,
  `context orient` and `response` stable and versioned; the effect-class map
  complete for every verb exposed.
- **Scope:** resources `state`, `board`, `next`, `conformance`, `knowledge`
  (read-only projections). Read-only tools `status`, `next`, `validate`,
  `context orient`, `response style`. Then write tools `claim`, `checkpoint`,
  `transition` and ticket operations, each a thin call into the engine.
  Excluded from v1: `ship`, `push`, `clean`, `goal`, Git effects, arbitrary
  shell.
- **RED / GREEN:** a tool that writes `.saipen/` directly is caught by a guard
  test; the same fixture driven through the CLI and through MCP yields
  byte-identical `.saipen/`; killing the server mid-write recovers through the
  existing journal; with the server absent the CLI is unchanged.
- **Measure, do not assume:** cold-start bytes for `context orient` versus the
  raw Markdown read, on this repository and on a small one. The source's
  "-40..70%" is a hypothesis.
- **Verify before building:** the current MCP specification revision, the
  stdio transport, and whether the skills extension the source cites exists as
  described. The source names revision 2026-07-28; that was not verified here.
- **Non-goals:** network, daemon requirement, authentication.
- **Rollback:** delete the server entry from the host configuration.

### S3 — MCP v2: structured continuation

- **Defect class:** the first answer to a cold agent is prose it must parse.
- **Scope:** one structured continuation payload (phase, active ticket,
  `next_action`, blockers, capability, conformance, recovery state) as the single
  machine answer; capability negotiation mapped onto the adapter registry's
  `declared_strength` and `response_enforcement`; progress and subscriptions
  for viewers; `response render|check|style` exposed so a host with no hook
  (today ADVISORY) can obtain the same verdict on demand; publish the protocol
  rules with the server only if the specification supports it.
- **RED / GREEN:** an ADVISORY host that calls the exposed check refuses the
  same invalid reply the hooked hosts refuse; payload schema versioned and
  parity-tested against the CLI.

### S4 — Multi-host coordination gate

- **Only on measured demand:** two agents writing one project at once, or two
  machines. Without it the stage stays closed.
- **Order is fixed by the existing design:** registry, then lease broker, then
  read-only eligibility (`future_architecture/12_ROADMAP.md`). A remote MCP
  transport is placed after the lease broker, as a single serialization point
  (one server plus the SAIOPS lock per project). Disconnected writers remain
  out of scope; that boundary is documented, not fixable here.
- **Remote security list (each item its own RED control):** authentication,
  authorization, project isolation, path validation, per-tool permissions, rate
  limits, audit, TLS. Dangerous verbs stay operator-gated (I4).
- **Gate:** a threat model and a hostile-input matrix before any listener
  exists.

### S5 — Cloud: a product gate before an engineering gate

- **Milestone 1 is not a server.** It is one person willing to pay for one
  hosted function. Until that exists, no infrastructure is built and the stage
  costs nothing.
- **Split:** open source keeps the protocol, CLI, validator, local MCP and the
  single-machine Git workflow, free. Candidates to sell are the ones the local
  version deliberately lacks: hosted registry and MCP endpoint, encrypted state
  backup, cross-machine continuation, agent presence and claims, dashboard,
  notifications, team permissions.
- **Invariant test:** cloud unreachable means local behavior unchanged (I1, I3).
- **Signals, not targets** (the source's illustration, before tax and fees):
  a few hundred euro monthly covers tool subscriptions; independence from
  other income needs several months of stable revenue, not one good month.

## 6. Friction check across stages

| Stage | The person no longer has to | The agent no longer has to guess |
|---|---|---|
| S0 | check which copy of the rules a host loaded | which EXECUTION.md is real |
| S1a | audit logs for leaked credentials by eye | whether a value is safe to write |
| S1b | notice that enforcement quietly vanished | whether a refusal is a fault or a limit |
| S1c | fear a power cut mid-checkpoint | whether recovery state is trustworthy |
| S1d | pay full protocol cost on a toy project | whether SAIPEN applies at all |
| S2-S3 | brief each new host | root, transport, next command |
| S4 | serialize agents by hand | whether another writer is live |
| S5 | run their own coordination service | nothing new; must not regress local |

## 7. Decisions owed by the owner, not by an agent

1. The commit policy for the dirty tree, which gates S0.
2. Whether to install the Claude Code hook and remove the hand-written
   `UserPromptSubmit` hook.
3. Whether the lite profile (S1d) belongs before MCP v1 (S2).
4. Whether S5 is an intention or an idea to keep parked.

## 8. What this roadmap does not do

It does not reorder BOARD, grant publication or ownership, treat an estimate as
a measurement, restate the multi-project architecture, or turn any stage into a
single implementation wave.
