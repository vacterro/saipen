# SAIPEN command reference

Conditional API appendix to COMMANDS.md. The original command forms and owner
references are preserved below. REGISTRY.json and COMMAND_EFFECTS.json own
machine facts; the referenced owners retain semantics. This appendix is not an
independent rule owner or an authorization grant.

## Shortcut table

| Input | Routes to | Rule ref | Notes |
|-------|-----------|-----------------|-------|
| `gg` | `saipen goal` | CMD-ROUTING-01 | NEW GOAL ONLY; `gg <objective>` names it, and it is never a continuation alias -- `cc` resumes |
| `hh` | `saipen hunt` | CMD-ROUTING-01 | Autonomous defect/improvement scan |
| `ff` | `saipen focus` | CMD-ROUTING-01 | Read-only closer inspection |
| `xx` | `saipen cut` | CMD-ROUTING-01 | `xx confirm <CUT-ID>` authorizes the planned mutation |
| `vv` | `saipen build` | CMD-ROUTING-01 | Bounded foreground Work |
| `zz` | `saipen undo` | CMD-ROUTING-01 | Restore the last safe milestone |
| `cc` | `saipen continue` | CMD-CONTINUE-01 | It enters convergence from `normal` and resumes `execution_intent: goal`, and it never asks for an objective; `cc <args>` is not a goal |
| `ccc` | `saipen continue` | CMD-CONTINUE-01 | Converge target `ship`, then refresh stages J-M |
| `st` | `saipen stop` | CMD-ROUTING-01 | Checkpoint and return control; `ss` retired |
| `sss` | `saipen status` | CMD-ROUTING-01 | Read-only status |
| `dd` | `saipen plan` | CMD-ROUTING-01 | Plan; payload supplies user items |
| `aa` | `saipen markhunt` | CMD-ROUTING-01 | Dry audit; records, never fixes |
| `qq` | `saipen prepare saiwiki` | CMD-ROUTING-01 | Force-fresh wiki package |
| `qqq` | `saipen collect saiwiki` | CMD-ROUTING-01 | Integrate ready wiki package, then ship |
| `ee` | `saipen prepare saitranslate` | CMD-ROUTING-01 | Force-fresh translation package |
| `eee` | `saipen collect saitranslate` | CMD-ROUTING-01 | Integrate ready translation package, then ship |
| `pp` | `saipen sub spawn saipython` | CMD-ROUTING-01 | Python tooling role |
| `tt` | `saipen test` | CMD-ROUTING-01 | Run the declared suite, read-only |
| `sc` | `saipen crew` | CMD-ROUTING-01 | Serial full-platoon convergence circuit |

## Canonical commands (non-shortcut)

| Command | Phase / Action | Rule ID |
|---------|---------------|---------|
| `saipen set` | INIT | CMD-ROUTING-01 |
| `saipen init` | INIT | CMD-ROUTING-01 |
| `saipen continue` | router | CMD-CONTINUE-01 |
| `saipen goal <text>` | PLAN | CMD-ROUTING-01 |
| `saipen clean` | Enter CLEAN; completion waits for the phase's exit obligations | CMD-ROUTING-01 |
| `saipen translate` | TRANSLATE | CMD-ROUTING-01 |
| `saipen validate` | Core conformance | CMD-ROUTING-01 |
| `saipen prepare <producer>` | PREPARE | CMD-ROUTING-01 |
| `saipen collect <producer>` | router | CMD-ROUTING-01 |
| `saipen ship` | SHIP | CMD-ROUTING-01 |
| `saipen push` | SHIP | CMD-ROUTING-01 |
| `saipen improve [action]` | meta | CMD-CONTINUE-01 |
| `saipen improve [status\|sweep-queue\|verify] <cycle>` | DIAGNOSTIC: read-only derived lifecycle status, the exact unswept composite finding queue in deterministic order, and the bounded DELTA audit; status refuses to round malformed evidence up to a normal lifecycle state (IMPROVE.md) | CMD-ROUTING-01 |
| `saipen improve reconcile <cycle>` | BUILD/RECOVERY: strict-cycle finite exit; classify every seat, execute lossless transitions, refuse while actionable work remains, terminalize COMPLETE/SUPERSEDED/BLOCKED_EXTERNAL; idempotent | CMD-ROUTING-01 |
| `saipen status` | read-only | CMD-ROUTING-01 |
| `saipen storage [status\|classify\|durable\|ephemeral\|scratch\|store\|verify\|promote\|migrate]` | Durable/scratch policy, stores and promotion; `status`/`classify`/`verify` and every `show` action are DIAGNOSTIC, the set/remove/declare/promote actions are EXECUTION and `migrate` is RECOVERY; STORAGE.md lists the exact forms | STORE-SAFETY-01 |
| `saipen response render\|check --stdin`, `saipen response style [--json]` | response gate; `style` prints the chat contract generated from STYLE.md | EXEC-RESPONSE-01 |
| `saipen admission status\|check\|matrix --session S --host H` | read-only: admission state (UNBOUND, BINDING, ADMITTED, STALE, REFUSED, DEGRADED) / per-host enforcement boundaries | PROTOCOL-ADMISSION-01 |
| `saipen admission establish\|invalidate --session S --host H` | host-hook transport only: the separated authority admits the host's own hook invocation, never a shell or a direct import | PROTOCOL-ADMISSION-01 |
| `saipen autonomy` | read-only: the supervisor's ONE verdict (RUN_WORK, ADOPT_WORKER, REPLACE_WORKER, AWAIT_WORKER, OPERATOR_ACTION_DUE, NO_PROGRESS_LOOP, AMBIGUOUS_AUTHORITY, IDLE) plus the observation that produced it -- lease generation and heartbeat age, executable Work, due/deferred operator gates, no-progress verdict. Writes nothing; ambiguous lease authority fails closed for mutation | CMD-ROUTING-01 |
| `saipen autonomy recall` | read-only AUTO_RECALL + turn-entry decision for a replaced/cold agent (RUNTIME.md) | CMD-ROUTING-01 |
| `saipen gpu [status\|on\|off\|index\|recall <text>\|triage]` | DIAGNOSTIC: idle-GPU lane, default OFF (`SAIPEN_GPU=off` wins); a local embedding model indexes Work/decisions/knowledge, a local chat model annotates red declared-family runs (mechanical groups, one hypothesis each), both while the card is idle and beside `supervise`; ADVISORY only, writes only `.saipen/cache/` (gpu.py) | CMD-ROUTING-01 |
| `saipen lock [status]` | DIAGNOSTIC: read-only holder of the project writer lock (PID, command, since) or free; never acquires, creates or deletes it (lock.py) | CMD-ROUTING-01 |
| `saipen context orient [--handoff JSON]` | bounded current-truth orientation | CONTEXT-BUDGET-01 |
| `saipen brief` | generated handoff with identity/lineage/event provenance | CONTEXT-BUDGET-01 |
| `saipen mail [init [--workspace PATH]]` | per-user SAIMAIL mailbox binding (SRC-136), DIAGNOSTIC status; `init` provisions the internal default idempotently via `saimail-local saipen init`; internal letters only | CMD-ROUTING-01 |
| `saipen acceptance <T-###>` | read-only | CMD-ROUTING-01 |
| `saipen test suite [declare -- <command>\|run [T-###]\|withdraw]` | a project's ONE declared suite, engine-run into a typed record (actions: EXECUTION); digest suite totals: only its current-tree record, never LOG prose | CMD-ROUTING-01 |
| `saipen runtime` | read-only | CMD-ROUTING-01 |
| `saipen host bootstrap [--host ID] [--project-root PATH]` | read-only host/runtime binding diagnostic; `HOST_UNSUPPORTED` for unregistered hosts | CMD-ROUTING-01 |
| `saipen host activation --project-root PATH` | read-only; does the managed project's resolved runtime carry the activation contract | CMD-ROUTING-01 |
| `saipen host entry [--host ID] [--project-root PATH] [-- <command>...]` | transport only: proven transport or `PROJECT_UNBOUND`/`RUNTIME_UNAVAILABLE`/`HOST_UNSUPPORTED`; with a command, rebinds a dead home, then runs it as argv, never via a shell; unregistered hosts: DIAGNOSTIC only | CMD-ROUTING-01 |
| `saipen rebind-home --auto` | RECOVERY: converge a dead persisted home onto an already-proven runtime (`HOST_BINDING_CONVERGED`; refuses `HOME_REQUIRED` when nothing proves) | CMD-ROUTING-01 |
| `saipen rebind-home <candidate-home-path>` | RECOVERY: explicit re-point of `STATE.saipen_home` onto a proven install | CMD-ROUTING-01 |
| `saipen search <pattern>` | read-only bounded search | CMD-ROUTING-01 |
| `saipen host doctor\|repair\|mode [strict\|degraded\|default]\|launcher\|machine` | no project: read-only host state / RECOVERY reinstall / admission policy / machine runtime | HOST-INTEGRATION-01 |
| `saipen host instructions [status\|repair]` | SAIPEN block in a project's `AGENTS.md`: verdict / RECOVERY marker-to-marker rewrite; creates none | CMD-ROUTING-01 |
| `saipen --agent <seat> launch <host> -- [args]` | optional explicit-actor host process (registry `launch_executable`) | CMD-ROUTING-01 |
| `saipen knowledge [status\|index\|retrieve]` | project knowledge | CMD-ROUTING-01 |
| `saipen future [status\|list\|next]` | DIAGNOSTIC: deferred authority candidates (FUTURE.md) -- lifecycle counts, per-gate verdicts, and the ONE deterministic next candidate; writes nothing | FUTURE-GATE-01 |
| `saipen future refresh` | EXECUTION: rebuild `.saipen/future/index.json` from the `future_gate/` corpus by identity (id > digest > title), never by filename alone, then recompute each gate's readiness. Routing runs this itself whenever the projection is not CURRENT, so a NEW document in `future_gate/` needs no import command | FUTURE-GATE-01 |
| `saipen future refine FG-#### [--slice TEXT --evidence PATH[,PATH]]` | EXECUTION: ONE ambiguous document/verdict: classify its own recorded status into the closed vocabulary; write the bound .saipen/future/records/FG-####.json. Never rewrite source or grant implementation. --slice/--evidence bind undeclared prose facts. Router runs once/chain when no ELIGIBLE gate and ambiguity exists (FUTURE.md) | FUTURE-GATE-01 |
| `saipen future promote FG-####` | INGRESS: ONE ELIGIBLE bounded slice via ordinary start receipt/dedupe/seat/goal valve. Ineligible/already-owned refuses; residual stays deferred; gate closes only after all slices resolve (FUTURE.md) | FUTURE-GATE-01 |
| `saipen future add <title> [--body TEXT] [--priority P0-P3] [--evidence PATH[,PATH]]` | INGRESS: deferred authority candidate, default DEFERRED; never Work, rule source or implementation authority alone (FUTURE.md) | FUTURE-GATE-01 |
| `saipen start '<task>' [--file PATH] [--hex HEX] [--receipt SRC-###]` | THE entry command for a new actionable task: capture, recover, seat, claim | CMD-ROUTING-01 |
| `saipen handoff <T-###> --to <agent> [--authority SRC-###]` | Owner or operator-authorized live claim transfer; same Work and phase | CMD-ROUTING-01 |
| `saipen user-request <text>` | USER_INTERRUPT ingress | CMD-ROUTING-01 |
| `saipen ticket compact <T-###>` | RECOVERY: compact one historical BOARD record to its minimum truthful form (OPS.md) | CMD-ROUTING-01 |
| `saipen ticket retire <T-###> --reason <CODE> --evidence <E-###\|.saipen/evidence/PATH> --authority <SRC-###> [--discovery-event E-###] [--note TEXT]` | canonical retirement of misrouted/invalid Work -- NOT done, NOT close; the authority must GRANT it (OPS.md) | CMD-ROUTING-01 |
| `saipen work reverify T-### [--contract FILE]` | RECOVERY: RV; OPS.md | CMD-ROUTING-01 |
| `saipen work contracts [T-###] [--limit N] [--offset N]` | DIAGNOSTIC: closed dependencies; OPS.md | CMD-ROUTING-01 |
| `saipen work regression <T-###> --file <contract.json>` | EXECUTION: owned VERIFY pair (phases/verify.md) | VERIFY-ORACLE-01 |
| `saipen ticket resolve-external <T-###> --authority <lineage-32hex> --implementation <T-###@commit> --reason <CLASS> --run <command>...` | EXECUTION: close BLOCKED Work implemented by an external authority with an immutable `EX-NNNNNN` receipt bound to the installed engine generation (OPS.md) | CMD-ROUTING-01 |
| `saipen ticket renew-external <T-###> --implementation <T-###@commit> --verification-contract <path> --paths <p1,p2> [--external-root <path>] [--runtime-inputs <absolute-paths>]` | EXECUTION: renew DONE external proof with authenticated current checks and an immutable predecessor binding (OPS.md) | CMD-ROUTING-01 |
| `saipen ticket repair-metadata <T-###> --field source_receipts (--to <SRC-###> \| --legacy-unbound [--authority <SRC-###\|lineage-32hex>])` | RECOVERY: DONE-only malformed legacy source_receipts migration. --to needs exact linked receipt; --legacy-unbound removes unprovable token, preserves bytes in immutable MR-NNNNNN. Non-DONE or conflicting second migration: zero-write refusal (T-1435) | CMD-ROUTING-01 |
| `saipen ticket reasoning <T-###> --recurrence <text> --weak-model <text>` | EXECUTION: canonical writer for the strict-sweep reasoning gates; refuses unless a strict CONFIRMED PROTOCOL_VIOLATION disposition names the ticket | CMD-ROUTING-01 |
| `saipen ticket requires <T-###> <CAP[@PHASE[+PHASE]],...\|read_only\|none>` / `saipen ticket regression <T-###> required [--evidence executed]` | EXECUTION: Work capabilities (RUNTIME.md) or strengthen non-DONE regression metadata; executed profile in phases/verify.md | CMD-ROUTING-01 |
| `saipen cohort [status\|ship] <C-###>` | batch publication authority | CMD-ROUTING-01 |
| `saipen cohort reconcile <C-FINAL> --from <C-OLD[,C-OLD]> --review-work <T-###>` | RECOVERY: preserve pending member history while a current reviewed cumulative batch adopts its publication obligation; OPS.md owns the bounds | CMD-ROUTING-01 |
| `saipen ticket bind-cohort <T-###> --cohort <C-###> --paths <p1,p2>` | RECOVERY: verified, unpublished own_patch DONE into pending cohort; preserve original row/finish/history and active Work. Exact retry byte-noop; published/legacy/foreign/conflicting bindings refuse (OPS.md) | CMD-ROUTING-01 |
| `saipen source` | intake | CMD-ROUTING-01 |
| `saipen source capture (--file <UTF8_FILE>\|--hex <UTF8_HEX>\|-- <TEXT>)` | INGRESS: the ingress half of the audit-inbox contract -- persists ONE verbatim source body and a receipt; an audit layer that reached `ingest` without it has no receipt to close (SOURCES.md) | CMD-ROUTING-01 |
| `saipen source req <SRC-###> <RID> <CLASS> <TEXT...> [--when-environment <HOST>]` | EXECUTION: add one requirement clause to a live receipt (SOURCES.md) | CMD-ROUTING-01 |
| `saipen source disp <SRC-###> <RID> <DISPOSITION> [--work T-###] [--evidence E-###]` | EXECUTION: adjudicate one clause to a disposition and bind its Work and evidence (SOURCES.md) | CMD-ROUTING-01 |
| `saipen source close <SRC-###>` | EXECUTION: prove a receipt's evidence and mint the tombstone; this is the ONLY verb that writes one, so it is the precondition of every later consume/archive (SOURCES.md) | CMD-ROUTING-01 |
| `saipen source archive <SRC-###>` | EXECUTION: move an already-CLOSED receipt's artifacts into the archive; refuses while the receipt is still active (SOURCES.md) | CMD-ROUTING-01 |
| `saipen source purge <SRC-###> --confirm` | EXECUTION: destroy an ARCHIVED receipt's cold bytes; the explicit `--confirm` is mandatory and its absence is CONFIRMATION_REQUIRED, not a preview (SOURCES.md) | CMD-ROUTING-01 |
| `saipen source retire <SRC-###> --reason <CLASS> [--successor SRC-###] [--note TEXT]` | EXECUTION: receipt-only retirement; preserve cold original bytes; unresolved clauses or live Work refuse (OPS.md) | CMD-ROUTING-01 |
| `saipen source link <SRC-###> --work T-###` | EXECUTION: one durable Work membership, primary preserved; idempotent. Unknown receipt/Work or integrity failure: zero writes (T-1437) | CMD-ROUTING-01 |
| `saipen source append [--to <SRC-###>] [--class APPEND\|SUPERSEDE\|CLARIFICATION\|CONFLICT] [--delta implementation\|evidence\|review\|packaging\|context] [--supersedes <ID,...>] [--label TEXT] (--file <PATH> \| --hex <HEX> \| -- <TEXT>)` | INGRESS: ONE verbatim immutable mission append (T-1461): amends, exact-digest dedupe, ordered per-source ledger; original source unchanged (SOURCES.md) | CMD-ROUTING-01 |
| `saipen source apply-append <SRC-###>` | EXECUTION: project the oldest RECEIVED append into requirements, Work and the minimum truthful rewind; idempotent and crash-resumable; what it supersedes becomes SUPERSEDED, never deleted (SOURCES.md) | CMD-ROUTING-01 |
| `saipen source appends` | DIAGNOSTIC: read-only per-mission append view status shares -- latest append, active and superseded clause counts, unprojected appends, affected Work | CMD-ROUTING-01 |
| `saipen source delta <SRC-###>` | DIAGNOSTIC: read-only classification of the UNADMITTED worktree delta against the receipt's clauses -- exact changed-file identity and observed stamps, NOT_EXECUTED verification, publication authority CLOSED; admits, settles and writes nothing (SRC-325 §10) | CMD-ROUTING-01 |
| `saipen source recover` | DIAGNOSTIC: read-only orphan/crash diagnostic; never deletes or invents source intent | CMD-ROUTING-01 |
| `saipen source reconcile <SRC-###> [--confirm]` | RECOVERY: read-only contradiction report; `--confirm` converges tombstone-authoritatively only on strong proof, else zero writes | CMD-ROUTING-01 |
| `saipen source normalize [--dry-run]` | RECOVERY: journal BOARD ranges as explicit receipt IDs; malformed ranges refuse; preview writes zero | CMD-ROUTING-01 |
| `saipen source quarantine <SRC-###> [--reason CODE]` | EXECUTION: preserve the exact active or archived body locally and exclude it from release/export; `--dry-run` previews without writing; does not close Work or waive coverage (SOURCES.md) | CMD-ROUTING-01 |
| `saipen authority capture --file <UTF8_FILE>\|--hex <UTF8_HEX>` | persist ONE operator-authority Source from exact bytes, including scoped gate decisions (OPS.md); never projects Work | CMD-ROUTING-01 |
| `saipen audit [status\|inspect\|trace\|ingest\|enqueue\|manifest]` | DIAGNOSTIC except EXECUTION `ingest`/`enqueue`/`manifest --write [--force]`; `inspect`/`trace`: N/filename (SOURCES.md) | CMD-CONTINUE-01 |
| `saipen userperson [show\|add\|remove\|reset]` | meta; direction is DEFAULT not ORDER (CORE.md), `reset` deletes the profile and needs `--confirm`, and `show --effective` is read-only (CORE.md) | CMD-ROUTING-01 |
| `saipen sub [spawn\|adopt\|sync\|pause\|resume\|clean\|collect\|dispose\|reconcile] <name>` | sub; `sync`/`spawn`/`adopt`/`pause`/`resume`/`clean`/`collect`/`dispose` are EXECUTION and `reconcile` is RECOVERY (CONVERGE.md, COMMANDS.md below) | CMD-ROUTING-01 |
| `saipen undo confirm` | EXECUTION: the confirmation leg of the `zz` milestone restore; without it the restore is a preview (CONTROLS.md) | CMD-ROUTING-01 |
| `saipen cut confirm <CUT-ID> -- <mutation>` | EXECUTION: authorize ONE already-previewed planned mutation; the preview alone writes nothing (CONTROLS.md) | CMD-ROUTING-01 |
| `saipen recover [inspect]` | DIAGNOSTIC: read-only recovery inspection; `resolve-blocker <SRC-###>` / `resolve-next-action <SRC-###>` consume scoped witnessed authority (OPS.md); `ab`/`aa`/`qq`: CONTROLS.md | CMD-ROUTING-01 |
| `saipen fleet [preflight\|scan\|prepare]` | install-scoped Fleet binding; `preflight` and `scan` are read-only, `prepare` is RECOVERY and the only mutating leg -- it refuses `--root` and is never a dry-run, and `scan` inspects ONLY the explicit roots it is given and never enumerates children | CMD-ROUTING-01 |
| `saipen sub reconcile <role> --authority <SRC-###>` | RECOVERY: producer terminal reconciliation (T-1435). A: DONE producer/BOARD proves all Work terminal; clear stale task/residue. B: truthful SCOUT/PLAN/BLOCKED projection, real open Work unchanged. Malformed STATE/BOARD or foreign owner: zero writes (CONVERGE.md, sub_lifecycle) | CMD-ROUTING-01 |
| `saipen campaign [status\|admit\|step\|cancel]` | `status` is DIAGNOSTIC (the current campaign's bounded budget, horizon and lifecycle state, writing nothing). `admit` is INGRESS: it records ONE campaign only under an explicit authority proof reference (`--grant`), a bounded resource budget (`--max-wall`/`--max-cycles`/`--max-generations`) and an admissible horizon, and refuses a reused campaign id without `--force-new`. `step` is EXECUTION: advances exactly one iteration and persists the dispatch request before any host is involved. `cancel` is RECOVERY. Every mutating subcommand refuses in a read-only capability, and all four refuse under `--dry-run` except `status` | CMD-ROUTING-01 |
