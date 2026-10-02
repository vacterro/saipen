# T-1553 F: per-host response-enforcement strength, measured 2026-09-28

Read-only evidence, and a correction of an earlier version of this file.

The earlier version printed the registry's `declared_strength` column and then
prose asserting that OpenCode's BLOCKING claim "now holds". That was a
declaration inspection presented as an enforcement result. It is replaced here
by the measured answer, per host, with the columns kept separate.

Two owners, and no third inventory added by this note:

- **declared** -- `extensions/adapters/registry.json`, `declared_strength` per
  adapter. What the adapter CLAIMS for an installed, current, healthy install.
- **effective** -- `tools/saipen_engine/admission.py::effective_strength`, the
  live computation on this machine. Its own contract, quoted in the registry:
  effective enforcement is "never stronger than the installed state proves".

Every `effective` cell below was produced by calling that function; none is
inferred from the `declared` cell. The `installed` / `current` / `effective`
columns are a MEASUREMENT OF THIS MACHINE AT THIS MOMENT and move when a hook
is installed or removed -- the `declared` column is the stable declaration.
`HostStrengthHonesty` therefore checks the `declared` cell of every host against
the registry on every run, and separately refuses any row that claims effective
BLOCKING where the live engine does not report it. Re-measure before quoting the
instrumental columns as a current fact.

## Measured per-host record

`installed` / `current` are the live hook state at the declared install
surface. `live proof` is a live-host refusal experiment; it is ABSENT for every
host, without exception, and that is stated per row rather than once in a
footnote.

| host | declared | hook artifact | installed | current | effective | mechanism | deterministic proof | live proof | unavailable boundary |
|---|---|---|---|---|---|---|---|---|---|
| opencode | BLOCKING | `plugins/saipen-guard.js` | no | n/a | **ENFORCEMENT_GAP** | `experimental.text.complete` + `tool.execute.before` | PRESENT -- `tools/test_t1553_mid_session_activation.py` drives the real plugin through node against a real guard, incl. REAL_INIT_SAME_TURN | ABSENT | no before-tool/Stop hook host trust; the hook is not installed at the declared surface on this machine, so the BLOCKING claim is **not** effective here |
| codex | ADVISORY | `hooks/saipen-guard.py` | yes | yes | **UNKNOWN** | Stop hook over `last_assistant_message` | PRESENT -- deterministic classifier/installer tests | ABSENT | `CODEX_STOP_REENTRY_NO_FAIL_CLOSED` (a Stop re-entry cannot guarantee terminal fail-closed correction) and `CODEX_STOP_TEXT_CLASSIFICATION`; live negative probe fails `helper_sandbox_lock_failed` / `SetNamedSecurityInfoW` 5, so no host trust is proven (T-1551, BLOCKED `HOST_EXECUTION_UNAVAILABLE`) |
| claude | ADVISORY | none shipped | n/a | n/a | ADVISORY | PreToolUse capability, no shipped hook artifact | declaration + capability only | ABSENT | no final-text hook surface shipped for this host |
| gemini | ADVISORY | `hooks/saipen-guard.py` | yes | yes | **UNKNOWN** | hook declared and installed; installer check unobservable | declaration + install-state only | ABSENT | `declared_strength: ADVISORY` with `blocking_capability: true`; the live function returns UNKNOWN rather than guessing |
| kiro | ENFORCEMENT_GAP | `hooks/saipen-guard.py` | no | n/a | ENFORCEMENT_GAP | hook declared, no proven host | none | ABSENT | no `kiro` command and no declared host home (T-1317, BLOCKED `BLOCKED_EXTERNAL`) |
| generic | ENFORCEMENT_GAP | none | n/a | n/a | ENFORCEMENT_GAP | none | none | ABSENT | no hook surface by definition |
| aider | ADVISORY | none | n/a | n/a | ADVISORY | instruction text only | declaration only | ABSENT | no before-tool and no final-text hook surface |
| antigravity | ADVISORY | none | n/a | n/a | ADVISORY | instruction text only | declaration only | ABSENT | no before-tool and no final-text hook surface |
| codebuddy | ADVISORY | none | n/a | n/a | ADVISORY | instruction text only | declaration only | ABSENT | no before-tool and no final-text hook surface |
| deepseek | ADVISORY | none | n/a | n/a | ADVISORY | instruction text only | declaration only | ABSENT | no before-tool and no final-text hook surface |
| freebuff | ADVISORY | none | n/a | n/a | ADVISORY | instruction text only | declaration only | ABSENT | no before-tool and no final-text hook surface |
| openai | ADVISORY | none | n/a | n/a | ADVISORY | instruction text only | declaration only | ABSENT | no before-tool and no final-text hook surface |
| qwen | ADVISORY | none | n/a | n/a | ADVISORY | instruction text only | declaration only | ABSENT | no before-tool and no final-text hook surface |
| zaicode | ADVISORY | none | n/a | n/a | ADVISORY | instruction text only | declaration only | ABSENT | no before-tool and no final-text hook surface |

## What this changes about the OpenCode claim

OpenCode is the only adapter whose response contract is *claimed* mechanically
blocking. On this machine `effective_strength("opencode")` returns
**ENFORCEMENT_GAP**, because its hook is not installed at the declared
surface -- the installed state does not prove the declaration. Reporting it as
BLOCKING would be exactly the inference the earlier version made.

What the mechanical proof does support, and no more:

1. **MATERIALIZATION_REBIND_PROVED** -- `MaterializationRebind`: a plugin
   instance whose bootstrap binding was resolved as `NOT_SAIPEN_PROJECT`
   re-asks the same canonical resolver and upgrades when bytes appear.
2. **REAL_INIT_SAME_TURN_PROVED** -- `RealInitSameTurn`: the real `saipen init`
   command is admitted through the real `tool.execute.before`, the host
   executes the real canonical INIT effect, and the final response of THAT
   SAME TURN is refused with `EXEC_RESPONSE_INVALID`; a canonical control
   surface passes; a later free-form completion in the same session is still
   refused; a replaced model does not escape it.

Both are deterministic proofs of the ADAPTER ARTIFACT under the real node
runtime. Neither is a live-host proof, and neither upgrades the effective
strength of an install that is not present.

## Pre-fix subject

The VERIFY-ORACLE-01 control is the un-repaired adapter artifact kept at
`.saipen/kitchen/t1553-prefix/saipen-guard.js`. Pointing the identical fixture,
oracle and assertions at it via `SAIPEN_OPENCODE_PLUGIN_UNDER_TEST` must admit
the free-form completions.

## Codex stays separate evidence (never laundered)

`extensions/adapters/codex.md` records two boundaries this note does not
upgrade: `CODEX_STOP_REENTRY_NO_FAIL_CLOSED` and
`CODEX_STOP_TEXT_CLASSIFICATION`. Codex's live `effective` reads **UNKNOWN**,
not BLOCKING: the hook is installed and current, but the installer check could
not be observed, and the function deliberately refuses to guess in that case.
T-1551 is BLOCKED on `HOST_EXECUTION_UNAVAILABLE`; no host trust is inferred
from deterministic tests.

## Open, and where it belongs

Hosts with no hook surface are instruction-level only. Whether any of them can
gain a mechanical final-response gate is not asserted here: that needs a
supported host event and a live proof per host, which is T-1551's shape of
work, not a documentation change.
