# T-1935 — the ZAICODE guard hook needed an owner that deploys AND sees it

Ticket: T-1935 (P1)
Filed from: T-1934's live check, 26.10.26
Verify criterion: *"saipen runtime --prelaunch --adapter zaicode reports
hook_problems:['hook-stale'] for a drifted installed hook and resyncs it to the
shipped bytes; saipen host doctor reports the same drift instead of current; a
test proves the prelaunch verdict and the injector's hook step both reach the
ZAICODE hook surface, and the existing no-write-into-the-user-profile contract
in test_t1504_zaicode_adapter still holds or is explicitly reconciled"*.

## What was wrong

ZAICODE was the only adapter shipping a `hook_artifact`
(`extensions/adapters/zaicode/saipen-guard.py`) while declaring **neither**
`install.hook` **nor** `hook_installer`. That single omission had two
consequences, and neither showed up as a failing test:

1. **Nothing deployed the hook.** `bootstrap/inject.ps1` runs its Copy-Hook
   step only under `if ((Has-Prop $install 'hook') -and $install.hook)`, and
   `bootstrap/inject.sh` invokes an installer only when the registry's
   `hook_installer` column is non-empty. Both gates were empty for ZAICODE, so
   the canonical injector installed the skill and the instruction block and
   silently skipped the guard. The T-1933 repaired artifact reached the live
   surface only because it was installed by hand — which is why a green ticket
   did not stop the 20-ticket valve from tripping again.
2. **Nothing observed the hook.** `runtime_bootstrap.hook_problems` begins
   `if not artifact or not surface: return []`. With `install.hook` unset,
   that is a permanent `[]`: no drift, ever. `host_integration._hook_facts`
   routes to the installer only when `hook_installer` is set, and otherwise
   falls through to exactly that blind function. Both observers wired into the
   prelaunch gate therefore reported a byte-drifted hook as current, while
   `autoinject.hook_status` — which reads `hook_install_surface` directly —
   correctly said `stale`. Two observers, opposite answers, one of them on the
   launch path.

Measured on a throwaway home with `USERPROFILE`, `HOME` and `ZAICODE_HOME`
redirected, using the same drifted bytes:

| observer | before repair | after repair |
|---|---|---|
| `runtime_bootstrap.hook_problems` | `[]` fresh, `[]` drifted | `[]` fresh, `["hook-stale"]` drifted |
| `runtime_bootstrap.prelaunch(resync=False)` | `ok:True` | `ok:False code:RUNTIME_STALE hook_problems:["hook-stale"]` |
| `host_integration.doctor` hook status | `current` either way | `current` fresh, `stale` drifted (`artifact-stale`) |

## The repair

### 1. The registry declaration

`extensions/adapters/registry.json`, ZAICODE entry only:

- `"hook_installer": "tools/install_host_guard.py"` — names the deployer the
  other four installer-managed adapters already use;
- `"install".hook = "~/.zcode/hooks/saipen-guard.py"` — the same path
  `hook_install_surface` already declared, i.e. the file `cli/config.json`
  makes the running host execute as argv;
- `"hook"` added to `freshness_surfaces`;
- `hook_surface_note` recording the split and the reason, so the next reader
  does not "simplify" the hook back into the isolated home.

No deployment topology changed. ZAICODE's SKILL and INSTRUCTION surfaces stay
inside `$ZAICODE_HOME/.zcode`; only the hook lives in the operator profile,
because that is the file the host actually reads. This is the reconciliation T-
1504's contract needed: `tools/test_t1504_zaicode_adapter.py` previously
asserted `assertFalse((profile / ".zcode").exists())` — a blanket claim that
the injector never writes into the profile. That claim was true only while the
hook went undeployed. It now asserts the split precisely: nothing at the skill
or instruction surface inside the profile, and the hook present byte-for-byte
identical to the shipped artifact.

### 2. The false alarm the declaration exposed

Declaring `hook_installer` also changed WHICH checker `doctor` uses. It passes
the installed runtime copy (`_hook_facts` → `install(..., check=True)`), so the
expected argv names that copy, while the hook on disk correctly names the
canonical source — because that is what the installer writes. The ZAICODE
branch compared `args` exactly, so the `--saipen-root` value became contract and
the live host reported:

```
hook: stale   problems: ["config-entry-differs", "delegated-root-stale"]
```

on bytes that were already correct. That is worse than the blindness it
replaced: a permanent false alarm trains the operator to ignore the gate.

`install_host_guard._same_process_entry` now applies the rule every other branch
had already settled — T-1338 (the root is a spelling), T-1342 (the generation it
proves is contract), T-1624 (the interpreter is the Python that installed the
hook). Every other field and argument stays exact; a different root is accepted
only when it proves the same generation; a different interpreter only when it
exists on this machine.

The ZAICODE branch also reported `delegated_root` from the root it WOULD write
rather than the one the config names, which is why `root_current` was answering
about a hypothetical file. It now reads the owned entry, as every other branch
does.

Measured on the live host after both fixes: installer `current:true
problems:[]`, doctor `hook: current problems:[]`.

## Proof

`tools/test_t1935_zaicode_hook_ownership.py`, 12 tests, all green. Every fixture
is a temp directory; `isolate_host_session()` plus redirected
`USERPROFILE`/`HOME`/`ZAICODE_HOME` mean nothing here touches the operator's
real `~/.zcode`.

| test | what it pins |
|---|---|
| `test_the_adapter_declares_a_deployer_and_a_hook_freshness_surface` | the declaration exists and `install.hook` equals `hook_install_surface` |
| `test_the_skill_and_instruction_surfaces_stay_in_the_isolated_home` | the split's other half, still true |
| `test_the_canonical_installer_puts_the_shipped_hook_on_the_profile` | the deployer reaches the profile and writes shipped bytes |
| `test_the_injector_shell_hook_step_reaches_zaicode` | the `install.hook` predicate the injectors gate on |
| `test_runtime_hook_problems_sees_zaicode_drift` | `[]` fresh → `["hook-stale"]` drifted |
| `test_prelaunch_refuses_a_drifted_zaicode_hook` | `ok:False` / `RUNTIME_STALE` / names the hook |
| `test_prelaunch_resync_restores_the_shipped_hook_bytes` | `RUNTIME_RESYNCED`, bytes restored, problems cleared |
| `test_doctor_flips_the_zaicode_hook_from_current_to_stale` | `current` → `stale` with `artifact-stale` |
| `test_a_different_root_spelling_with_a_proven_generation_is_accepted` | the false alarm: a different root spelling reads current |
| `test_a_root_that_proves_no_generation_is_still_stale` | the tolerance's limit, at the comparison |
| `test_the_root_tolerance_hides_no_real_drift` | both observers still see stale bytes, a bogus root and a tampered field |
| `test_removing_the_declaration_blinds_prelaunch_and_doctor` | **RED control** — strip the two keys and the same drifted bytes read `current` again |

Two of these are red controls, and they are the important ones. Every other test
passes whether or not the repair is load-bearing, because they all exercise the
repaired state. `test_removing_the_declaration_blinds_prelaunch_and_doctor`
removes `install.hook` and `hook_installer` and asserts the blindness returns;
`test_the_root_tolerance_hides_no_real_drift` asserts that loosening the argv
comparison did not also stop the three real drifts from registering. A future
edit that drops a key or widens the tolerance cannot look harmless.

Focused evidence record:
`.saipen/evidence/focused-unit/e960b6c9016705ff-20261026T202358982655Z.json`
— 91 tests PASS across `test_t1935_zaicode_hook_ownership`,
`test_t1504_zaicode_adapter`, `test_t1624_host_integration` and
`test_t1934_deploy_staleness`.

Neighbour suites re-run after the registry and installer changes, all green:
`test_adapter_parity`, `test_guard_admission`, `test_runtime_generation_identity`,
`test_t1584_production_zcode_boundary` (94 tests, 1 skip), plus
`test_t1624_host_integration`, `test_t1934_deploy_staleness`,
`test_t1504_zaicode_adapter` (79 tests).

## Live host, after the repair

```
tools/install_host_guard.py zaicode --check
  current: true  problems: []  root_current: true
  artifact: C:\Users\vac34\.zcode\hooks\saipen-guard.py
  config:   C:\Users\vac34\.zcode\cli\config.json

saipen host doctor --host zaicode
  state: STALE_RUNTIME   hook: current   problems: []
```

`STALE_RUNTIME` is the honest remaining verdict: the installed ZAICODE skill
copy is behind the source after this ticket's edits. That is the fleet-wide
condition recorded below, not a hook defect.

## What this does NOT prove

- **No live-host acceptance.** The repair was verified against fixture homes and
  the shipped registry. Whether the operator's running ZAICODE process picks up
  a redeployed hook, and whether a restarted native ingress now accepts a
  `cc`, remain UNVERIFIED. R031/R032 forbid inferring live acceptance from a
  green fixture or a generation counter.
- **The valve is still spent.** `goal_tickets` stands at the cap for the
  ZAICODE session. This ticket repairs the mechanism that will *notice* and
  *redeploy* drift; it does not and cannot reauthorize the counter. Per
  SRC-339:R006 the only sanctioned route is a fresh operator `cc` through a
  restarted native ingress.
- **`opencode` is not covered.** It ships a hook artifact and a
  `hook_install_surface` but no `hook_installer`; it is deployed by its
  injector, and `test_adapter_parity` treats that as its own arrangement. This
  ticket makes no claim about its observability.
- **The fleet runtime copies are behind.** After this ticket's edits, every
  installed skill copy is one generation behind the source (`opencode` and
  `claude` at 19-20 changed files, `zaicode` and the rest likewise).
  `saipen host repair` would resync them; it is a separate act with its own
  authorization, and the dry run lists nine hosts. Doctor reports the condition
  honestly in the meantime.
