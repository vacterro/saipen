# T-1859 / SRC-291 — what is proven, and the one thing that is not

Status after BUILD + VERIFY on 2026-10-24.

## Proven by measurement (AC-02, AC-03, AC-04)

233 tests green (`verify-run.log`), and a durable broker-level control
(`control.py`, 5/5, `red-control.log`) that proves five facts no assertion could
carry:

| # | fact | result |
| --- | --- | --- |
| A | the shipped binding (`os.getppid()` = the host pid) is refused | `worker is not an observed child of the proven native host` |
| B | registering the hook itself succeeds | ok |
| C | a **sibling** shell engine cannot spend the seal | `operator origin or delivering OS worker is unverified` |
| D | the hook's **own child** engine verifies | ok |
| E | a second spend is idempotent, not a new grant | action `continue` |

## The defect and the cure

`extensions/adapters/zaicode/saipen-guard.py` registered `os.getppid()`. ZAICODE
spawns a hook straight from the host's own execution port
(`spawn(prepared.command.file, …)` in `node-execution-adapter-run.js`), so the
hook's parent IS the host process — the very pid
`host_authority_identity` proves as `host_pid`. `operator_origin.register_worker`
refuses exactly that, so sealing failed on every genuine prompt and the
operator's own cc was recorded as `model_supplied`. That is the reported loop.

The cure has two halves, and the second is what makes the first usable:

1. register `os.getpid()` — the host's own hook child;
2. renew a spent budget from the engine the hook starts, because the broker
   accepts a verifier only below the registered worker (fact C). The agent's
   shell can never be that process.

Installed through the canonical `install_host_guard.install`: `current=True`,
`problems=[]`, installed bytes identical to the shipped artifact
(`sha256 613cf7195f1c9a2b`). The broker's own currency check compares those
bytes, so a stale install would have refused the cure.

## The live defect, observed in production

The gap above is narrower than it was: a genuine host delivery WAS captured and
it is the pre-fix subject this ticket needs.

`pre-fix-live-envelope.json` (copied verbatim from
`_9router_extra/.saipen/cache/ingress/ing-da4df1aa5446268b.json`) carries

- `session_id: sess_03e89c14-…` and `message_id: turn_70dddf8f-…` — real host
  identifiers, so the hook ran on a real prompt and read it correctly (T-1868's
  half is confirmed in production);
- `declared_by: host_ingress` — the admission path itself declares it;
- `witness: model_supplied` — the seal did NOT happen.

Feeding that same text to `operator_task.witness` returns
`reset_bounded_authority: False`. That is the reported loop reproduced end to
end with production data: the host delivered the operator's words, the hook
read them, and the origin was not sealed, so the valve could not clear.

It was written `2026-10-24 03:31:22` local, three minutes **before** the cure was
installed at `03:34:36`. One operator prompt exists after the install
(`03:36:57`, same session) but it is still `admitted`, never `promoted`, so no
turn — and therefore no hook run — followed it. No post-fix genuine event exists
yet, which is why AC-01 stays open.

## A defect found in my own cure, and fixed

`saipen continue --json` pretty-prints (`indent=2`). `_renew` originally scanned
stdout line by line for a one-line `{…}` object, so a successful renewal would
have been reported `RENEWAL_UNREADABLE` — a silent success-shaped failure, the
same class of bug as the one being cured. It now decodes the whole stream and
falls back to the last single-line object. Measured before the fix against real
AUDAPACK: `{"ok": false, "code": "RENEWAL_UNREADABLE"}`; after:
`{"ok": false, "code": "RECONCILE_REAUTH_REQUIRED"}` — the engine's true answer,
correctly refusing a sibling shell. Two tests pin it, one of which restores the
one-line reader and asserts it fails.

## Not proven: AC-01 [LIVE]

Requires a fresh genuine operator `cc` sent from the deployed ZAICODE UI to
AUDAPACK, with the original event/root/session and actual worker identity
observed. Measured state of the world:

- host prompt ledger: newest genuine prompt `2026-10-23 18:32:17`; the sole
  prompt after the install (`2026-10-24 03:36:57`) was admitted but never
  promoted, so no turn ran;
- the fix was installed at `2026-10-24 03:34:36`, after the only post-install
  hook-eligible event, so **zero** sealed-prompt opportunities have occurred;
- broker log: 82 lines, every one a shell refusal, **zero** hook entries;
- the one live envelope that does exist is the pre-fix subject above.

So the live outcome is *unobserved*, not failed. It cannot be produced by a
model: SRC-291 says verbatim that "Test doubles and source-only changes cannot
satisfy this LIVE outcome", and its DO-NOT list forbids fabricating a witness or
spoofing provenance.

## The exact manual step (for the operator, once)

Send `cc` from the deployed ZAICODE UI while sitting in
`V:/___VAC/__K/__CODE/_PY/_AUDAPACK` (that project's own STATE is at
`0 waves / 30 tickets -- run 'cc' to continue`). Expected after the cure:

- the hook reports `"sealed": true` with an `operator_origin`;
- STATE/BOARD/LOG show the valve cleared canonically (`goal_waves`/`goal_tickets`
  reset) and work resumes through the normal router.

No terminal command is required of the operator: the renewal runs inside the
hook's own process tree, which is the only place the broker will accept it.


## Bounds

Every measurement here is re-runnable. The process-topology facts are simulated
in `control.py` in the real shape (host -> hook, host -> shell -> engine); they
are not a claim to have observed a live host event. AC-01 remains open until
such an event exists.


## Live event reconciliation (2026-10-24 04:41 local / 01:41Z)

The operator sent `cc` at 04:41 local from deployed ZAICODE into AUDAPACK.

### Exact observed event trace
- Hook executed: PID 15224 at 01:41:19Z, PID 9916 at 01:41:51Z
- Ingress admitted: `ing-bc5281527413187b.json` in AUDAPACK `.saipen/cache/ingress/`
- `message_id`: `01a16b91-cbcf-7dd0-9aa7-6afc0267827e`
- `session_id`: `sess_b1f5a223-d1d5-4c67-81fe-6e35fad94641`
- `request_text`: `cc`
- Broker log entry at 01:41:19Z:
  `{"at": "2026-10-24T01:41:19Z", "chain": ["python.exe", "zaicode.exe", "zaicode.exe", "zaicode.exe", "zaicode.exe", "autohotkeyu64.exe"], "code": "BROKER_CLIENT_NOT_AUTHENTICATED", "event": "client_refused", "host": null, "op": "register-origin-worker", "pid": 15224, "step": "NOT_HOST_DESCENDANT"}`

### First failing boundary
- Outcome: **H. worker registration failed**.
- Root cause:
  1. `HAC.issue_operator_origin` returned `{"ok": True, "code": None, "proof": {...}}`.
  2. `saipen-guard.py` passed the response envelope `origin` directly to `HAC.register_operator_worker(origin, worker)`.
  3. `register_operator_worker` evaluated `proof.get("host")`, which was `None` because `"host"` is nested inside `origin["proof"]`.
  4. The request arrived at the broker with `"host": null`.
  5. Broker `identify()` fell back to default `HOST_IMAGES` (`claude.exe`), failed to recognize `zaicode.exe` in the process ancestry, and refused with `NOT_HOST_DESCENDANT`.
  6. Sealing was aborted (`sealed = False`), so hook-child `_renew()` did not execute and the ingress was recorded as `model_supplied`.

### Implemented corrections
1. `extensions/adapters/zaicode/saipen-guard.py`: extract `proof = origin.get("proof") if ... else origin` before calling `register_operator_worker` and sealing `envelope["operator_origin"]`.
2. `tools/saipen_engine/host_authority_client.py`: unwrap `proof.get("proof")` and resolve `host` from `proof_dict`.
3. `tools/saipen_engine/host_authority_broker.py`: fallback to resolving `host` from `payload.get("proof")` when `"host"` is omitted.
4. `tools/saipen_engine/operator_origin.py`: `register_worker` and `revoke` accept wrapped or unwrapped proof.
5. `tools/test_t1859_zaicode_seal.py`: updated stub client to reflect the real nested broker return shape.
6. Synchronized installed artifacts:
   - `C:\Users\vac34\.zcode\hooks\saipen-guard.py`
   - `C:\Users\vac34\.claude\skills\saipen\extensions\adapters\zaicode\saipen-guard.py`
   - `C:\Users\vac34\.claude\skills\saipen\tools\saipen_engine\host_authority_client.py`
   - `C:\Users\vac34\.claude\skills\saipen\tools\saipen_engine\host_authority_broker.py`
   - `C:\Users\vac34\.claude\skills\saipen\tools\saipen_engine\operator_origin.py`
