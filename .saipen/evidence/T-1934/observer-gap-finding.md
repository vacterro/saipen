# T-1934: the deploy gap is closed; the OBSERVER gap is not

Measured 2026-10-26 while closing T-1934. Read-only probes; nothing in the
operator's hosts was written by the investigation.

## 1. What T-1934's verify criterion asked for, and what now holds

The criterion has two halves.

**Half A — "`--check` reports `current:true` with no `artifact-stale` for every
adapter whose source artifact changed since its last install".** Measured live
via `.saipen/evidence/T-1934/live-check.log`:

| host | shipped digest | installed surface | byte-identical | `--check` |
| --- | --- | --- | --- | --- |
| claude | `2a5955eb10ecd679` | `~/.claude/hooks/saipen-guard.py` | yes | `current:true problems:[]` |
| codex | `b69c2a413d2c1122` | `~/.codex/hooks/saipen-guard.py` | yes | `current:true problems:[]` |
| gemini | `dbba552643a3657b` | `~/.gemini/hooks/saipen-guard.py` | yes | `current:true problems:[]` |
| zaicode | `4317be7fc0175157` | `~/.zcode/hooks/saipen-guard.py` | yes | `current:true problems:[]` |
| kiro | `dbba552643a3657b` | absent | n/a | `artifact-missing` (host never set up) |
| opencode | `8cd916664244d868` | `~/.config/opencode/plugins/saipen-guard.js` | yes | n/a — deployed by the injector, not this installer |

The one non-current row is a host that is not installed on this machine, which
is `artifact-missing`, not a stale deploy. T-1933's own artifact
(`extensions/adapters/zaicode/saipen-guard.py`, sha `4317be7f`) is on the live
ZAICODE surface byte-for-byte, which is the condition whose absence made the
20-ticket valve keep tripping.

**Half B — "a test proves a source-artifact edit makes a previously-installed
hook read stale AND that the post-install surface matches the source
byte-for-byte".** `tools/test_t1934_deploy_staleness.py`, 5 tests, green:

* `test_a_source_artifact_edit_makes_an_installed_hook_read_stale` — per host
  (`claude`, `codex`, `gemini`, `kiro`, `zaicode`): install, assert current,
  edit the SHIPPED artifact, assert `current:false` with `artifact-stale`
  while `installed` and `configured` stay true and `effective` is
  `ENFORCEMENT_GAP`;
* `test_redeploy_puts_the_shipped_bytes_on_the_surface` — after re-install the
  surface equals the shipped bytes exactly and the next check is
  `current:true problems:[]`;
* `test_the_check_cli_separates_current_from_drifted` — the same verdicts
  through the CLI an operator runs;
* `test_the_matrix_covers_every_host_the_installer_accepts` — pins the matrix
  to the installer CLI's own accepted set, so a host cannot fall out of
  coverage silently;
* `test_a_blinded_byte_comparison_would_call_a_drifted_hook_current` — the RED
  control: with `content_bytes` blinded the same drifted fixture reads
  CURRENT, proving the verdicts come from the shipped-bytes comparison.

## 2. The gap this does NOT close (measured, filed separately)

`install_host_guard.py` detects drift correctly, and the injector calls it for
every adapter that declares `hook_installer`. ZAICODE declares neither
`hook_installer` nor `install.hook`:

    zaicode   install.hook=None   installer=None   freshness=[skill, instruction]
    claude    install.hook=~/.claude/hooks/...    installer=tools/install_host_guard.py   freshness=[skill, instruction, hook]
    codex     install.hook=~/.codex/hooks/...     installer=tools/install_host_guard.py   freshness=[skill, instruction, hook]
    gemini    install.hook=~/.gemini/hooks/...    installer=tools/install_host_guard.py   freshness=[skill, instruction, hook]
    kiro      install.hook=~/.kiro/hooks/...      installer=tools/install_host_guard.py   freshness=[skill, hook]

Consequences, each reproduced in a throwaway home with `USERPROFILE`/`HOME`
redirected:

1. `bootstrap/inject.ps1` / `inject.sh` reach the hook step only under
   `(Has-Prop $install 'hook') -and $install.hook`; for ZAICODE that is false,
   so the canonical injector deploys its skill and instruction block and never
   its guard hook. The fix that shipped in T-1933 reached the live surface
   only because it was installed by hand.
2. `runtime_bootstrap.hook_problems(zaicode, source)` returns `[]` no matter
   how far the installed hook has drifted, because it returns `[]` when
   `install.hook` is absent. Measured: same fixture, same drifted bytes —
   `[]` with the shipped entry, `["hook-stale"]` once `install.hook` was added.
   That function is what `saipen runtime --prelaunch` and `saipen host doctor`
   consult, so both report a drifted ZAICODE hook as current.
3. `autoinject.hook_status(zaicode)` DOES see the drift (`stale`), because it
   reads `hook_install_surface` directly. So the observers disagree, and the
   one wired to the prelaunch gate is the blind one.

The registry repair is not a one-field edit: `tools/test_t1504_zaicode_adapter`
asserts the injector writes NOTHING into the user profile for ZAICODE
(`self.assertFalse((profile / ".zcode").exists())`) while ZAICODE's live hook
lives at `~/.zcode/hooks/saipen-guard.py`, and the adapter's
`home_note` promises the isolated home. Declaring `install.hook` decides where
the hook belongs, which is a design question about ZAICODE's two-home split —
filed for its own ticket rather than changed at the end of a goal budget.
