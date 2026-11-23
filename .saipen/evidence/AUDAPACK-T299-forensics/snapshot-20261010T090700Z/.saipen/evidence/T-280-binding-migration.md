# T-280 — persisted Prepared/Scheduler bindings across the federation cut-over

Verify clause: *tests prove unambiguous re-point still runs, unmappable ⇒
BLOCKED/ACCOUNT_MAPPING_REQUIRED and does not run, no cross-identity re-point,
historical records stay readable.*

Scope of this evidence: hermetic controls (`tests/test_prepared_binding.py`, 22
tests), the RED proof below, and a read-only live check on the operator's
machine. Nothing here adds an account database, a credential store, or a second
`sa(i)-accounts list` reader.

## 1. RED proof — the defect on the tree before the repair

Script: two arms on a throwaway store, `PreparedWorker._settle_binding` in place
vs. neutered so the row is scheduled exactly as it was persisted.

```
prepared job legacy blocked: ACCOUNT_MAPPING_REQUIRED: no canonical account proves the identity claude2
unambiguous (claude1)    in place  launcher_id='sai:claude:profile-dir:aaaa'    state=WAITING_TRIGGER reason='time not reached'
unambiguous (claude1)    NEUTERED  launcher_id='claude1'                        state=WAITING_LIMIT   reason='account not discovered'
unmappable  (claude9)    in place  launcher_id='claude9'                        state=WAITING_LIMIT   reason='account not discovered'
unmappable  (claude9)    NEUTERED  launcher_id='claude9'                        state=WAITING_LIMIT   reason='account not discovered'
contradiction            in place  launcher_id='claude2'                        state=BLOCKED         reason='ACCOUNT_MAPPING_REQUIRED: no canonical account'
contradiction            NEUTERED  launcher_id='claude2'                        state=WAITING_LIMIT   reason='account not discovered'
```

Reading the contradictions row: the row names account `claude1` and launcher
`claude2`, only `claude1` is provable. The repair refuses to migrate the half it
can prove and BLOCKS the row; neutered, the row is silently re-scheduled with
its unusable binding and dies later in the launch path.

Mechanism controls, same script run against the tree BEFORE the repair
(`/tmp/red280.py`, captured at SCOUT):

```
control 1  a binding resolver exists in the tree ...... False
control 2  a one-time binding migration pass exists .... False
control 3  JobState.BLOCKED exists .................... False
control 4  retired-row launch ........................ refused: PreflightError('launcher missing or disabled') (generic, retryable=False)
control 5  row still names the retired id ............ claude1 | ARMED | ''
```

Controls 1–3 flip to `True` after the repair. Controls 4–5 describe the raw
`build_launch_plan` seam, which is not where the repair lives: a retired row is
settled by the scheduler before that seam is ever reached, which is what the
first table above measures.

`unmappable (claude9)` is deliberately NOT blocked in either arm: `claude9` was
never an account-backed static identity, so it is a Class A local tool id and
AUDAPACK owns it. Only the six retired account-backed ids
(`ACCOUNT_BACKED_LEGACY_IDS`) are ever re-pointed.

## 2. Green suite — `tests/test_prepared_binding.py` (24 tests)

```
$ python -m pytest tests/test_prepared_binding.py -q -p no:cacheprovider
........................                                                 [100%]
24 passed in 0.50s
```

What the 24 controls hold, in the words of the ticket:

- **unambiguous re-point moves the binding only.** `good` (account `claude1`,
  launcher `claude1`) becomes `sai:claude:profile-dir:aaaa`; its trigger,
  payload, enablement and state are untouched, and the live tick path does the
  same re-point.
- **unmappable ⇒ BLOCKED and does not run.** State `BLOCKED`, reason prefixed
  `ACCOUNT_MAPPING_REQUIRED`, `launcher_id` and `account_id` left exactly as
  persisted, and the worker's tick returns before scheduling.
- **no cross-identity re-point.** Two aliases resolving to different accounts,
  a half-provable pair, a canonical account contradicted by its launcher, a
  launcher naming a foreign account, and an unprovable identity all end
  `ACCOUNT_MAPPING_REQUIRED`. A provider match is never an identity match.
- **historical records stay readable.** `store.list()` still returns the blocked
  row, with its original ids and enablement; nothing is deleted.
- **a failed read decides nothing.** `proven=None` (no authoritative snapshot)
  leaves every row as it was; `proven=set()` (an authoritative snapshot without
  the account) blocks. The distinction is the outage clause of the
  specification, made explicit in the API.
- **one refresh owner.** a source-level control asserts the resolver and the
  migration pass contain no `subprocess`, `snapshot(`, `read_registry(` or
  `sai_accounts` reference, so neither can spawn its own plane read.
- **standalone is unaffected.** With `federation.active` false the worker never
  settles bindings, so a machine that has never federated keeps its local rows.
- **the re-pointed id is real.** On a federated config the migrated
  `sai:<account_id>` id is accepted by `resolve_launch_target(..., prepared=True)`.
- **a finished row is history.** A `DONE`/`MISSED`/`CANCELLED`/`FAILED_TERMINAL`/
  `DISABLED` row is never re-pointed and never retro-labelled `BLOCKED`, by the
  pass or by the worker: rewriting what a finished job says it did is rewriting
  evidence.

## 3. Live machine — read-only

```
prepared store: C:\Users\vac34\AppData\Local\AUDAPACK\state\resources.sqlite3 exists: True
persisted rows: 0
plane ok: True generation: 27 accounts: 7
proven accounts: 7 | legacy donors proven: 5
binding states: {'OK': 0, 'MIGRATED': 0, 'ACCOUNT_MAPPING_REQUIRED': 0}
federation: active=True stale=False generation=27 last_sync=2026-10-06T02:27:58.423389+00:00
effective rows: 11 | sai: rows: 7
store unchanged: True (e33214c08a1a0301 == e33214c08a1a0301)
```

The machine currently has zero persisted Prepared rows, so there is nothing to
migrate live: the pass is a no-op by data, and the behaviour above is proven
hermetically. The store fingerprint is identical before and after the run, and
the script never called the migration pass — it only resolved. No account was
added or removed, and no credential was read.

## 4. Residuals, not silently claimed

- **SYNC member bindings.** `prepared_sync_members` rows carry their own
  `launcher_id` alongside the canonical `account_id`, from the pre-federation
  era. A stale member id already fails closed (the group is written `BLOCKED`,
  never launched against a substituted account), but its reason is generic
  rather than `ACCOUNT_MAPPING_REQUIRED`. Not migrated in T-280; recorded as a
  follow-up rather than fixed under this ticket's verify clause.
- **A terminal row's trigger is still re-evaluated by the tick's static branch.**
  Pre-existing engine behaviour, unchanged by this repair and not caused by it: a
  `DONE` row whose account is not discovered is re-saved as `WAITING_LIMIT`
  (`account not discovered`) rather than left `DONE`. It cannot launch anything
  (the account is absent), and this repair deliberately does not touch it. Worth
  its own ticket rather than a silent fix here.
- **The UI shows the reason, not a dedicated BLOCKED affordance.** The Prepared
  widget renders `state.value: waiting_reason`, so an operator sees
  `BLOCKED: ACCOUNT_MAPPING_REQUIRED: …`. A first-class badge, filter and
  "Choose account" action belong to the UI convergence ticket (T-278).
