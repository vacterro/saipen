# ZAICODE adapter

Native ZAICODE needs no wrapper, seat, launcher or environment variable. Start
it the way you always do. This file is the **integration contract** SRC-342 R009
asks for: the actions the installed hook knows, the exact input form each one
requires, what the authority answer looks like, and the codes that mean "not
admitted". The product agent never has to guess a spelling or mint a proof.

## Two homes, on purpose

- **Hook and instruction surfaces are the operator profile's:** the hook is
  `~/.zcode/hooks/saipen-guard.py`, its config entry lives in
  `~/.zcode/cli/config.json`, and ZAICODE runs it as argv with `shell:false`.
  That is the file the running host reads, so that is where the installer writes
  it.
- **Skill and instruction text stay inside `$ZAICODE_HOME`** (an isolated
  `~/.zcode`), per `home_note` in `extensions/adapters/registry.json`. Without
  that split a SAIPEN integration edited the same profile a production ZCode
  uses.

Shipped artifact: `extensions/adapters/zaicode/saipen-guard.py`. Installer:
`python tools/install_host_guard.py zaicode`.

Boot route: the skill copy under `$ZAICODE_HOME/.zcode/skills/saipen/` carries
`SKILL.md` -> `saipen/BOOT.md`, which is the cold-start kernel a bare
`saipen continue` needs. `saipen/STYLE.md` is part of that boot read: apply it
before any output, not only when a rule question comes up. `RFC.md` is a
three-line redirect stub and holds no rules; the constitution lives in
`saipen/CORE.md`.

## Supported native actions

The hook maps one operator message to exactly one of three actions. It reads
the operator's own bytes -- the same `request_text` the broker digests -- and
never a field that names an intent.

| Operator types | Action | What must be true |
| --- | --- | --- |
| `cc`, `сс`, `/cc`, or any text that is not the two forms below | `continue` | nothing; this is the default and the only action for prose |
| `gg <objective>`, `saipen goal <objective>`, `saipen gg <objective>`, `/goal gg <objective>`, `/saipen goal <objective>` | `goal` | the command is a single command whose head resolves to the goal route |
| an exact goal-authorization JSON capsule | `authorize-goal` | it parses as an object whose `kind` is `saipen-goal-continuation`; the broker still requires it to equal `goal_authority.current_binding` |

Deliberately **not** promoted: a bare `goal <words>` ("goal of this task is X"
is prose), `/goal cc all` (the native spelling of the continuation), `ggg ...`,
`hh ...`, a multiline handoff that happens to begin with `gg`, and any text
over 256 KiB. Classification delegates to
`tools/saipen_engine/cold_recovery.py:goal_objective_text` so there is one
parser, not a second alias table drifting beside the canonical one.

The objective that gets bound is the objective text, never the whole command
line. `operator_origin` derives `goal_target` with `goal_ingress_identity` over
that objective, so the broker target and the `saipen goal` ingress agree. A
capsule whose contents differ from the live binding is refused rather than
renamed.

## What the hook answers

One JSON object on stdout. Exit status is 0 even for a refusal: ZAICODE reads
the answer, not the status.

```json
{
  "ok": true,
  "sealed": true,
  "authenticated": true,
  "seal": {"ok": true, "stage": "sealed", "code": "SEALED",
           "category": "authenticated", "detail": "..."},
  "destination_op": "continue"
}
```

`ok` is admission. `sealed`/`authenticated` is the broker half, and they are a
separate verdict on purpose: a green admission over an unsealed origin is how a
genuine `cc` used to be recorded as `model_supplied`. `seal.stage` is
`issue-origin`, `register-worker`, `envelope` or `sealed`; `seal.category` is
`authenticated`, `refused`, `unavailable`, `untrusted` or `conflict`. A sealed
`goal` adds `goal_entry`; a sealed capsule adds `goal_authorization`. `renewal`
appears only when a sealed continuation cleared a spent budget, and only
because the hook spends it from a process below the worker that registered the
proof.

## Known blocker codes

What the operator or the product agent may see, and what each means:

- `PROJECT_UNBOUND` -- the event's `cwd` has no `.saipen/STATE.md` above it.
  Nothing was sealed; there is no project to admit into.
- `HOOK_COMMAND_FAULT` -- the hook's own command line is unreadable. Nothing was
  evaluated.
- `ENGINE_UNREACHABLE` -- the installed runtime could not be imported. The hook
  answers rather than crashing, because an interpreter handed a broken script
  exits nonzero and ZAICODE reads that as a hook blocking every prompt.
- `ORIGIN_SERVICE_UNAVAILABLE`, `WORKER_SERVICE_UNAVAILABLE` -- no broker is
  listening, or it did not answer inside the 27 s hook budget. Starting the
  service repairs this.
- `ORIGIN_ENDPOINT_UNTRUSTED` / `WORKER_ENDPOINT_UNTRUSTED` -- the endpoint
  answered but failed server identity verification. Never "repaired" by
  restarting it: the endpoint is the problem.
- `ORIGIN_ENDPOINT_CONFLICT` -- another process holds the endpoint.
- `ENVELOPE_NOT_SEALED` -- the proof authenticated but was not bound to the
  delivered envelope.
- Any other code -- the broker answered and refused; its own exact code is kept
  verbatim. Do not translate it into a different story.

## Authority status

Read-only, from the project root:

    saipen status --json            # continuation_authority, authority_source, phase, task
    saipen host doctor              # per-host runtime/hook state, read-only
    saipen host repair --host zaicode --dry-run   # what a scoped repair would do

`continuation_authority: operator_required` with `safety_valve_mode: hard_wait`
is the bounded state: work proceeds until the 20-ticket checkpoint and then a
human decides. `operator_persistent` with `authority_until:
continuous_maintenance` is only legal when `goal_authority.prove` walks the
goal pivot journal, the committed entry record and the separated broker. A
hand-edited STATE claiming persistence is refused, not believed.

## Freshness and deployment

`saipen host doctor` reports the installed hook's digest against the shipped
artifact. The manifest ships `extensions/adapters` as a **copy tree**, so an
artifact that is present on one disk and absent from every clone makes the
canonical validator FAIL: `runtime manifest names a file git does not track`.
Stage and commit the adapter before refreshing any vendored bundle or installed
hook -- never publish an uncommitted working tree as the protocol source.

`saipen host repair --host zaicode --dry-run` scopes a deployment to this host
and states in its own output that it performs "no install, no authority restart,
no machine runtime write". No other agent's host is restarted by default.

## Known limits

Recorded rather than hidden:

- No final-response or delivery hook surface is installed. Chat style and
  protocol admission reach the model as instructions; there is no pre-render
  interception and a Stop hook cannot retract streamed text.
- `host_thought_visibility_control` is `UNAVAILABLE` -- native thought UI is
  host-owned.
- The anchor is what the operating system reports about live processes. It is
  not a boundary against code injected into the host process or a same-user
  process that rewrites the installed hook.
- A stale installed hook stays stale until someone commits the shipped bytes
  and runs the scoped repair. `saipen host doctor` names that state as
  `STALE_RUNTIME` / `BROKEN` rather than reporting a comfortable green.
