# T-1342 runtime-generation integrity boundary -- BUILD/VERIFY evidence

Executor: Claude Opus 5 (inherited seat `codex`, STATE.agent). Date: 2026-09-15.

## Defects closed in this wave (on top of the codex T-1342 draft)

| Class | Defect (pre-fix subject) | Fix owner |
|---|---|---|
| C | `bootstrap/inject.ps1` `Get-RuntimeFingerprint` + `$ProvenanceSurface` + `$InstallerGeneration`: private fingerprint over saipen.py + registry + manifest + engine `*.py`; label duplicated | injectors ask `runtime_surface` / `runtime_bootstrap.GENERATION` through the source tree's engine and verify the installed copy's identity |
| C | `bootstrap/inject.sh` `runtime_fingerprint()` + `INSTALLER_GENERATION`: same private definition | same |
| C | `runtime_surface.installed_runtime_identity` digested the installed tree over the CANONICAL inventory: an extra installed module was invisible; prelaunch `stale` ignored `fingerprint_match` | installed side proven over its own inventory; `fingerprint_match` is the verdict |
| C | `autoinject --check` verdict = stamp digest written into the candidate | content identity of each home; stamp is provenance (`UNSTAMPED` line) |
| C | `autoinject.distribution_report` stale = `source_head` mismatch + surfaces; installed content never read | per-home `runtime_generation` vs `expected_generation`, launcher, hook delegated root |
| C | `autoinject._manifest_surface` + `surface_drift` own cache filter + duplicate `installed_relpath` | `runtime_surface.surface_delta` / `installed_relpath` |
| defect | instruction block naming `<snapshot>/saipen` (the real installed shape) read STALE forever under the codex draft: the protocol dir was hashed as a flattened root | `protocol_home_runtime_root` |
| defect | OpenCode plugin hook freshness never checked the engine it executes (`skills/saipen`) | `_hook_state` delegated root |
| fail-open | junction/symlink in the unresolved chain, junction directory inside a tree, unlistable directory (os.walk silently skipped), duplicate/colliding landing names, dst drift, empty tree, missing required phase doc, ambiguous layout, NUL-bearing UTF-8 normalised | `runtime_surface` + `manifest.copy_tree_members` |
| harness | T-1327 launch test patched `tools.saipen_engine.runtime_bootstrap` while `host_launch` imported `saipen_engine.runtime_bootstrap`: real prelaunch (resync) + real `opencode.exe` with no timeout -> suite hang | patch the exact module + installer/host nets |
| harness | outer host-session carriers bound disposable fixtures (11 families red under a valid foreign binding) | `tools/test_hermetic_env.py` module isolation |

## VERIFY-ORACLE-01 red/green pair

Verifier: `oracle_probe.py` sha256 `6d72bb700970847e234ad8f25fd537797295760a55ba2b17e363bde2726573d2`
(identical fixtures; only the imported implementation varies).

Pre-fix subject: the OpenCode home installed from the pre-session worktree,
identity `gen-sha256:a2cb4177d2889db780dc03b6762138062ef371627bd5f68b0acb8a60d888bd32`.

| Probe | pre-fix | current |
|---|---|---|
| P1 stamp+head current, engine stale -> distribution fresh | true (RED) | false |
| P2 copied current stamp over stale bytes -> `--check` rc | 0 (RED) | 1 |
| P3 extra installed module, valid marker -> prelaunch | RUNTIME_CURRENT (RED) | RUNTIME_STALE |
| P4 current snapshot protocol dir is a real home | false (RED, false STALE) | true |
| P5 junction as declared tree root -> identity None | false (RED) | true |
| P6 NUL payload CRLF vs LF -> identities differ | false (RED) | true |
| P7 two names on one landing path -> identity None | false (RED) | true |

## T-1327 regression oracle timeout -- root cause

`TargetCRuntimeFreshnessTests.test_supported_launch_refuses_to_start_a_host_on_unproven_bytes`
patched `rb.prelaunch` where `rb` came from `from saipen_engine import runtime_bootstrap`
(bound to `tools.saipen_engine.runtime_bootstrap` under the tools/__init__.py alias),
while `host_launch` (imported as `saipen_engine.host_launch`) relative-imports
`saipen_engine.runtime_bootstrap` -- a second module object. The patch missed, the real
prelaunch ran (resync=True: the operator's installed runtime can be reinstalled from the
working tree) and `launch_host` started the real host with no timeout. Observed process
tree: `python -m unittest tools.test_t1327_zero_manual_recovery` -> `cmd /c opencode.CMD`
-> `opencode.exe` -> `codebase-memory-mcp.exe`; after the host was killed the test
failed `HostLaunchRefusal not raised`. A 09:56 `pytest tools` run from an earlier session
had been stuck on the same launch for eight hours (orphan `opencode.exe` PID 1360,
killed). The `TargetDFleetOutputSchemaTests` fault test runs in 0.1 s alone.
Harness fix: patch the exact module `prelaunch_runtime` imports, plus installer and host
`subprocess.run` nets. The alias defect itself is production code not caused by T-1342:
filed as T-1343. Module: 34 tests, 11.5 s (unbound), 11.3 s (hostile), 11.0 s (foreign lineage).

## Test isolation matrix

| Env | Carriers | Result |
|---|---|---|
| A unbound | none | 32 modules OK |
| B valid foreign binding | ROOT=AUDAPACK copy, LINEAGE=its real lineage, AGENT=buffy, CAPABILITY=read-only | 25 isolated OK; 7 non-isolated red -> isolated -> B2 7/7 OK |
| C foreign lineage | ROOT=SAIPEN repo, LINEAGE=lineage-0123..., AGENT=foreign-seat | 13 binding-sensitive OK |

No module created a repository-root file; no module changed SAIPEN STATE/BOARD/LOG/MANIFEST.

## Distribution (scheduled injector, HEAD ef654110)

`inject.log` 18:46: clean surface, all six homes copied, provenance `verified` for every
provenance home, `=== end rc=0 ===`. `autoinject --check`: `fresh: 6 agent home(s) at
gen-sha256:d05f4b69d16a65107ebb79e9f82e6a4a0b5ac7435865cfd1fb18a20a6a268c05`.

| Home | Runtime generation | Instruction home -> root | Hook delegated root | Launcher | Decision |
|---|---|---|---|---|---|
| .config (opencode) | d05f4b69 | scheduled-source\saipen -> scheduled-source (d05f4b69) | skills\saipen (d05f4b69) | ok | CURRENT |
| .claude | d05f4b69 | scheduled-source (d05f4b69) | -- | ok | CURRENT |
| .codex | d05f4b69 | scheduled-source (d05f4b69) | -- | ok | CURRENT |
| .gemini | d05f4b69 | scheduled-source (d05f4b69) | --saipen-root scheduled-source (d05f4b69) | ok | CURRENT |
| .codebuddy | d05f4b69 | -- | -- | ok | CURRENT |
| .agents (freebuff) | d05f4b69 | .knowledge.md -> scheduled-source (d05f4b69) | -- | ok | CURRENT |

Expected generation (clone at HEAD) = scheduled-source = every provenance marker
`runtime_fingerprint` = d05f4b69; marker `installer_generation`
`T-1342-runtime-surface-identity-20260915.1`. distribution `fresh: true`, 0 stale, 0 unknown.

## Live installed-runtime acceptance (Target H)

Installed CLI `~/.config/opencode/skills/saipen/tools/saipen.py`, disposable projects,
disposable USERPROFILE copies for the delegated-root cases: 14/14 OK in 4.8 s --
status boots; `fleet preflight --json` 1301 bytes, BOUND_VALID; read ADMITTED_READ_ONLY;
canonical STATE write refused PROTECTED_CANONICAL_NAMESPACE; `saipen recover --json`
ADMITTED; installed validator conformant, no FINDINGS_CAPTURE_FAILED, no layout error;
foreign `saipen_engine` on PYTHONPATH never executed; prelaunch RUNTIME_CURRENT on a
current copy, RUNTIME_STALE on a stale `admission.py`, RUNTIME_STALE on an extra module;
real home identity unchanged; source = installed = snapshot identity.
