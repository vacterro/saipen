# T-277 evidence — one effective launch inventory (red proof, hermetic green, live read-only)

## 1. RED proof — the controls fail when the repair is disabled

The repair is one function: `launch_federation.sync_effective_launchers`. Neutering it (answer `standalone`, touch nothing) restores the exact split-brain the source describes, and the controls fail:

```
  [FAIL(red)] every canonical account appears exactly once, keyed by account_id
  [FAIL(red)] no static Codex/Claude/Antigravity account authority remains
  [FAIL(red)] the canonical account is launchable with no manual static binding
  [PASS] one identity, one record (no local residue beside the projection)

inventory with the repair disabled: ['opencode', 'freebuff', 'cline', 'main_codex', 'main_codex2', 'main_codex3_free', 'claude1', 'claude2', 'antigravity', 'zcode']
controls red: 3/4
```

Control 4 (one identity, one record for `.claude`) stays green under the neutered reconciler on purpose: it guards the MERGE rule (an unbound local residue must not survive beside the bound canonical projection), which is exercised by the sync being disabled just as much as by it running. It is kept as a contract control, not as this repair's red evidence.

## 2. GREEN — hermetic suite

```
................................                                         [100%]
32 passed in 0.27s
```

## 3. LIVE read-only reconciliation against the installed registry

Run: `python audit/t277_live_reconciliation.py` (read-only; no account added, removed, hidden or launched; the config it reconciles is a throwaway in-memory AppConfig).

```
== T-277 LIVE, READ-ONLY ==
  [OK  ] 0 engine installed  -- C:\ProgramData\SAI\Accounts\bin\sai-accounts.exe

== A1: canonical snapshot (direct CLI) ==
       direct `sai-accounts list --all` exit=0
       generation=25 accounts=8 drawn=7 withheld=1
       A antigravity Antigravity 1      compact=AG1    backend=windows_user       state=ENABLED   hidden=False locator=opaque/fd325eb7
       A antigravity Antigravity 2      compact=AG2    backend=managed_windows_user state=ENABLED   hidden=False locator=opaque/7381b83a
       A claude      Claude 1           compact=CL1    backend=profile_directory  state=ENABLED   hidden=False locator=path/2e3528de
       A claude      Claude 2           compact=CL2    backend=profile_directory  state=ENABLED   hidden=False locator=path/bd16e951
       A codex       Codex 1            compact=CX1    backend=profile_directory  state=ENABLED   hidden=False locator=path/162bd834
       A codex       Codex 2            compact=CX2    backend=profile_directory  state=ENABLED   hidden=False locator=path/c98e8560
       A antigravity AG3                compact=AG3    backend=managed_windows_user state=ENABLED   hidden=False locator=opaque/ae55b59b
       W codex       Codex 3            compact=CX3    backend=profile_directory  state=DISABLED  hidden=False locator=path/bb193859
  [OK  ] A1 the payload is a real, non-empty registry  -- 7 drawn

== A2: authoritative read through production code ==
  [OK  ] A2 the production read succeeded  -- generation=25
  [OK  ] A2 production read == the plane's drawn set  -- read=7 drawn=7
  [OK  ] A2 a withheld account is not in the drawn set  -- withheld=['codex:profile-dir:6ac779b2bcd83465']

== A3: effective inventory == the canonical snapshot ==
       state=federated fresh=True generation=25
       added=['sai:antigravity:windows-user:1f17624fa8051f44', 'sai:antigravity:windows-user:407fdf8621212585', 'sai:claude:profile-dir:09ff6b999c422747', 'sai:claude:profile-dir:e46c08e5c03f7c99', 'sai:codex:profile-dir:ff7e3619f84e4e05', 'sai:codex:profile-dir:5c5ef150033ae3d8', 'sai:antigravity:windows-user:86e40a6e56585c5f']
       removed=['main_codex', 'main_codex2', 'main_codex3_free', 'claude1', 'claude2', 'antigravity']
       migrated=['main_codex', 'main_codex2', 'main_codex3_free', 'claude1', 'claude2', 'antigravity']
  [OK  ] A3 the sync reports a fresh federated read  -- federated
  [OK  ] A3 one row per drawn canonical account, same ids  -- rows=7 drawn=7
  [OK  ] A3 no duplicate row
  [OK  ] A3 no historical account-backed alias survives
  [OK  ] A3 every account row is keyed by its canonical account_id
  [OK  ] A3 no account row carries an operator command_template
  [OK  ] A3 local tools untouched  -- opencode,freebuff,cline,zcode
       launchable now: 4   honestly unavailable: 3
       UNAVAILABLE sai:antigravity:windows-user:1f17624fa8051f44 stage=
       UNAVAILABLE sai:antigravity:windows-user:407fdf8621212585 stage=
       UNAVAILABLE sai:antigravity:windows-user:86e40a6e56585c5f stage=
       execution backends: {'windows_user': 1, 'managed_windows_user': 2, 'profile_directory': 4}
  [OK  ] A3 a row is unavailable only when the plane exposed no usable context

== A4: idempotence ==
  [OK  ] A4 a second read changes nothing  -- added=[] removed=[]
  [OK  ] A4 order (the operator's) survived the second read

== B: plane absent (standalone) ==
  [OK  ] B no engine -> standalone, not stale  -- standalone
  [OK  ] B a plane that was never there mutates nothing

== C: control-plane outage ==
  [OK  ] C an outage is STALE, never 'no accounts'  -- stale
  [OK  ] C last-known-good projection kept
  [OK  ] C the flag says stale
  [OK  ] C no retired static alias came back
  [OK  ] C the outage did not forget the ledger  -- cache=7 last-good=7

== D: read-only ==
  [OK  ] D the operator's config and its neighbours are unchanged
  [OK  ] D the runtime state directory is unchanged
  [OK  ] D no NEW config backup was written

== SUMMARY ==
  all checks passed
```
