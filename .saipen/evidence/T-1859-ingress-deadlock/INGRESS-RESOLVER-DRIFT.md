# T-1859 field report: `RECONCILE_REAUTH_REQUIRED` on every ZAICODE `cc`

Reported by the operator, verbatim:

```
SAIPEN refuses this continuation and only the operator can clear it:
RECONCILE_REAUTH_REQUIRED — bounded run requires a fresh operator cc through
authenticated native ingress; WAIT: safety valve reached (0 waves / 23 tickets)
-- run 'cc' to continue (RECONCILE_REAUTH_REQUIRED)
(trusted ingress: the SAIPEN ingress hook is not installed for this host, so the
request travels without operator authority)
```

The parenthetical is the evidence. It is emitted by the **host**, not by SAIPEN.

## Producer

`ZAICODE/zcode/apps/zcode-cli/packages/bootstrap/src/zcode-protocol-v4/commands/operator-ingress.ts`

```ts
export function resolveOperatorIngressHook(env: NodeJS.ProcessEnv = process.env): string | null {
  const declared = env[OPERATOR_INGRESS_HOOK_ENV]?.trim();
  if (declared) return existsSync(declared) ? declared : null;
  const home = env.HOME?.trim() || env.USERPROFILE?.trim() || homedir();   // <-- source (uncommitted)
  const candidate = join(home, OPERATOR_INGRESS_HOOK_RELATIVE);            // ".zcode/hooks/saipen-guard.py"
  return existsSync(candidate) ? candidate : null;
}
```

`attemptOperatorIngress()` turns a `null` from this function into

```
state:  "trusted-ingress-unavailable"
detail: "the SAIPEN ingress hook is not installed for this host, so the request
         travels without operator authority"
```

and the CLI still sends `saipen continue --json`, which is exactly why the engine
then answers `RECONCILE_REAUTH_REQUIRED`: the bytes arrived, the sealed origin did not.

## The generation drift (byte-level)

| artifact | resolver body |
| --- | --- |
| source working tree (mtime 2026-10-23 09:31Z) | `env.HOME \|\| env.USERPROFILE \|\| homedir()` |
| **running** `resources/glm/zcode.cjs` (built 2026-10-23 07:09Z) | `e.ZAICODE_HOME?.trim()\|\|homedir()` |

Extracted from the shipped bundle:

```js
function CQa(e=process.env){let t=e[kQa]?.trim();if(t)return existsSync(t)?t:null;
let n=e.ZAICODE_HOME?.trim()||homedir(),o=join(n,".zcode","hooks","saipen-guard.py");
return existsSync(o)?o:null}
```

The source fix postdates the build and is **not committed** (`git status` on that
file: ` M`). So the running host still resolves the hook under `ZAICODE_HOME`.

## Why that directory is empty

```
ZAICODE_HOME = V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_ZAICODE\.zaicode\home
candidate    = ...\.zaicode\home\.zcode\hooks\saipen-guard.py     -> does not exist
```

That `.zcode` directory holds only `AGENTS.md`, `cli/`, `skills/`, `v2/` — there is
no `hooks/` at all. The hook is installed at its canonical surface instead:

```
C:\Users\vac34\.zcode\hooks\saipen-guard.py     (5306 bytes, byte-identical to
                                                 extensions/adapters/zaicode/saipen-guard.py)
```

So ZAICODE_HOME and the canonical install surface disagree, and the stale resolver
picks the wrong one.

## SAIPEN side is healthy, and correctly refuses my own probe

`python tools/install_host_guard.py zaicode --check`:

```json
{"host":"zaicode","capability":true,"installed":true,"current":true,"configured":true,
 "saipen_root":"V:\\...\\_SAIPEN","root_current":true,"problems":[],
 "artifact":"C:\\Users\\vac34\\.zcode\\hooks\\saipen-guard.py",
 "config":"C:\\Users\\vac34\\.zcode\\cli\\config.json"}
```

Hook self-test: `--self-test` exits 0 with no output.

Hook delivering a real envelope (executed):

```json
{"ok": true, "ingress_id": "ing-534d9b39e1d4cec2", "destination_op": "continue", "sealed": false}
```

`sealed: false` is **correct for this probe**, and is not a defect. I invoked the
hook from a shell tool call, so the ancestry contains `bash.exe`, not the host hook.
The broker says so exactly:

```json
{"code":"BROKER_CLIENT_NOT_AUTHENTICATED","reason":"HOOK_NOT_FOUND","op":"issue-origin",
 "detail":"the connecting process is under the host application but is not the installed
           host hook or the engine it started (a shell tool call is not a hook)"}
```

A shell cannot forge a sealed origin (SRC-291 DO NOT list). Sealing can only be
observed from a genuine host prompt, which is what T-1859 AC-01 asks for.

## Executed control on the shipped bytes

`control.js` requires `shipped-resolver.js` — the resolver body cut verbatim out of
`resources/glm/zcode.cjs` — and calls it with the live environment. Output
(`control.log`):

```
ZAICODE_HOME           : V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_ZAICODE\.zaicode\home
canonical hook exists  : true

RED   (no override)     -> null
GREEN (with override)   -> "C:\\Users\\vac34\\.zcode\\hooks\\saipen-guard.py"

RED reproduces the report : PASS
GREEN resolves the hook   : PASS

CONTROL HOLDS: the shipped resolver cannot find the hook, and the documented
override makes it find the canonical one.
```

`SAIPEN_INGRESS_HOOK` is the resolver's **first** branch, so it needs no rebuild:
it wins over the broken `ZAICODE_HOME` fallback. It has been persisted as a user
environment variable:

```
[Environment]::SetEnvironmentVariable('SAIPEN_INGRESS_HOOK',
    'C:\Users\vac34\.zcode\hooks\saipen-guard.py', 'User')
-> reads back: C:\Users\vac34\.zcode\hooks\saipen-guard.py  (5306 bytes, exists)
```

A host process must be **started** after the variable exists to pick it up; a host
already running keeps the environment it was launched with.

## What must change, and who can do it

1. **Deploy the resolver fix.** The corrected `HOME || USERPROFILE || homedir()`
   body must be committed and compiled into a new `resources/glm/zcode.cjs`.
   Until then the running host keeps looking under `ZAICODE_HOME`.
   The host's own parity guard already reports this:
   `ZAICODE_PARITY_STATUS=SOURCE_CHANGED_AFTER_BUILD`, remedy
   "Run REBUILD (or pnpm bundle:zaicode) ... and restart".
2. **Restart the host** so it inherits `SAIPEN_INGRESS_HOOK` (already persisted).
   That is enough on its own — no rebuild needed — because the override is the
   resolver's first branch and was proven above on the shipped bytes.
3. The broker accepts only the canonical artifact path
   `C:\Users\vac34\.zcode\hooks\saipen-guard.py`
   (`host_authority_broker.hook_artifacts("zaicode")`), so installing a second copy
   under `ZAICODE_HOME` would be refused as `HOOK_NOT_FOUND`, not accepted.
   A stray copy placed there during this investigation was removed again.

All three hook copies are byte-identical (`sha256:486a0d32408b9292…`): the
canonical install, the broker-root shipped artifact, and this worktree's source.

## The project that reports "23 tickets" is `_ZAICODE`, not AUDAPACK

Reproduced verbatim from `V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_ZAICODE`:

```json
{"ok": false,
 "code": "RECONCILE_REAUTH_REQUIRED",
 "message": "bounded run requires a fresh operator cc through authenticated native
             ingress; WAIT: safety valve reached (0 waves / 23 tickets) -- run 'cc' to continue",
 "operator_action": "Send fresh cc through authenticated native host ingress; an agent CLI
                     replay cannot renew this budget. Restore the host ingress bridge if it
                     is unavailable.",
 "required_ingress": "operator_carrier",
 "canonical_next_command": null}
```

Its STATE:

```
phase: REVIEW
task: T-417
next_action: "WAIT: safety valve reached (0 waves / 23 tickets) -- run 'cc' to continue"
saipen_home: "V:/___VAC/__K/__CODE/_AI_STUFF_AGENTIC/_SAIPEN"
execution_intent: goal
goal_waves: 0
goal_tickets: 23            <-- cap is 20 (goal_authority.limits.tickets)
continuation_authority: operator_required
authority_source: E-6406
authority_until: budget
safety_valve_mode: hard_wait
```

The two defects compose into the deadlock:

1. `_ZAICODE` processed 23 tickets against a 20-ticket cap, so the valve is legitimately
   tripped and only an operator-carried `cc` can renew the budget.
2. The operator's `cc` cannot carry authority, because the deployed host resolves the
   ingress hook to a path that does not exist.

Because of (2), every `cc` the operator types degrades to "the request travels without
operator authority", and the valve in (1) can never clear. That is the whole deadlock:
neither half is a SAIPEN bug, and neither half alone would block the operator.

## Separate observation: the running broker serves another install root

`host_authority_client.status()` reports

```
service: socket-named-pipe, pid 29064, ok: true
saipen_root: C:\Users\vac34\.claude\skills\saipen
runtime_root: C:\Users\vac34\.saipen\authority
```

This project's `saipen_home` is `V:\...\_SAIPEN`. The deployed broker was started
from the installed copy, not from this worktree. Not a blocker for the ingress
question above, but it means a worktree-side engine change reaches the authority
path only after that deployed copy is refreshed.
