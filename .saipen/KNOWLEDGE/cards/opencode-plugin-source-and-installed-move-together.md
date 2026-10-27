<!-- SAIPEN KNOWLEDGE CARD v1 -->
kind: trap
scope: extensions/adapters/opencode/saipen-guard.js, installed OpenCode plugin, declared core-unit family, test_opencode_host_smoke, SHIP evidence
trigger: editing the OpenCode guard plugin source, or a core-unit family red on test_fresh_process_loads_the_installed_generation_from_one_origin
status: active
evidence: T-1657, T-1568, .saipen/evidence/core-unit/17f266668a863f75-20261007T124215Z.json, tools/test_opencode_host_smoke.py, bootstrap/inject.ps1
supersedes: none

# The OpenCode plugin source and the installed plugin move together

After editing `extensions/adapters/opencode/saipen-guard.js`, refresh the copy installed in the machine profile before paying for the declared family, because `test_opencode_host_smoke` asserts the two are the same bytes and the family is red on that one test until they are.

Why:
The test reads `%USERPROFILE%/.config/opencode/plugins/saipen-guard.js`, compares its SHA-256 with the shipped artifact and then proves a fresh `opencode` process loads that generation. It is a statement about this machine, not about the delta, so no code fix makes it green: T-1657 lost one twenty-minute family run to it and T-1568 met it before. The refresh is the single step the injector performs for this host: copy the source file to that path and verify the digest is equal. Do it only when no `opencode` process is running, since a running host refuses its next tool call with `PLUGIN_RESTART_REQUIRED`; keep the previous file so the rollback is one copy; say in LOG that it was done. Do not run the whole injector for this: it publishes skills and runtimes to every host and refuses a dirty tree. The Claude hook has no such equality test in the family; its installed copy is refreshed by the operator through `saipen host repair`.
