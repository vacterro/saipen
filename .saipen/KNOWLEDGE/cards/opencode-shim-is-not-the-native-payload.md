<!-- SAIPEN KNOWLEDGE CARD v1 -->
kind: trap
scope: OpenCode native smoke, core-unit family, PATH, npm platform payload, verification environment
trigger: OpenCode smoke reports a Windows-incompatible executable or no startup probe despite a present command
status: active
evidence: T-1712, .saipen/evidence/core-unit/77a71a06679d26c4-20261011T065720Z.json, .saipen/evidence/AG3-runtime-20261011/opencode-instrument-control.json, .saipen/evidence/core-unit/77a71a06679d26c4-20261011T071900Z.json
supersedes: none

# Prove the native OpenCode instrument before paying for the family

Before the full family, inspect the selected entry and its package-owned native
payload, then execute the candidate's version and unchanged smoke controls.
A present command and matching plugin hashes do not prove startup. Use an
existing verified payload in the verification child's PATH; retain the first
red run and require the complete family, without weakening or skipping checks.

Why:
T-1712's default npm entry selected a 479-byte postinstall shell stub named
opencode.exe. Seven native checks were red because Windows never ran a native
host, although the real x64 payload was already present. Selecting that payload
only in the test process PATH produced 6156/0 red on the identical fingerprint,
without changing installation, source, plugin, tests or baseline. The failed
run cost 1472 seconds, repeating a failure already encountered under T-1708.

This differs from the installed-plugin freshness trap: both source and installed
plugin can match while the executable entry is unusable. Do not copy a plugin,
weaken a check, skip native coverage or run a global reinstall to conceal that
distinction. Re-prove the selected payload after upgrades; the recorded path,
size and version are historical observations, not permanent configuration.
