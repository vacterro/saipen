# T-1819 / SRC-278: current investigation checkpoint

The whole original mission remains active: actual Freebuff/Luna host input,
authenticated provenance, safe Auto-Doctor, original FastPrompter T-1479
recovery, regressions A-Q and real UI acceptance. No reduced definition of DONE
is adopted. SRC-278 is a complete body, not another title-only receipt.

## Confirmed owned defect

`model-env-negative-before.json` invokes the actual `operator_task.witness`
and `authority_for_provenance` in an isolated temporary root. Model-authored
text and its model-computed SAIPEN_TASK_SHA256, with a synthetic Freebuff marker,
produce operator_carrier and user_explicit/preempt/goal-pivot/reset authority.
No authenticated host event exists in that control. No real project authority
or source was modified. This contradicts the mission's B/M trust boundary.

The relevant code is `tools/saipen_engine/operator_task.py`: declared env
carriers are accepted by witness, and authority_for_provenance trusts the
operator_carrier/digest/declared_by tuple. The host_ingress cache path also
deserves inspection: admit_host_ingress and active_host_ingress are transport
helpers, not independent host authentication. Do not claim that a file, digest,
session string or declared_by field authenticates its creator.

The existing `test_freebuff_operator_provenance.py` B control omits a carrier;
M supplies unrelated USER_SAYS/LUNA_PROVENANCE variable names. Neither tests
forging the actual SAIPEN carrier names. Its positive A/D/O fixtures are
simulated, not a real authenticated UI boundary. Preserve truthful test classes;
do not use doubles to declare live acceptance.

Next implementation work must distinguish payload integrity from authenticated
operator authority. Reuse the existing separated host-authority owner if it can
bind the exact human event, task/digest, repository, session and bounded action.
A generic admitted model session is not proof that a particular task came from
the operator. Do not create same-user signing, a self-asserted proof flag, an
env-marker-only exception, a broker bypass or a mock-only positive.

## Actual installed Freebuff sources found

The old root handoff's generic names are not a concrete inspected call chain.
The current installed artifacts supply readable source:

- CLI: `C:/nodejs/freebuff.ps1` -> `node_modules/freebuff/index.js` ->
  `createLauncher` in `launcher.js`, version 0.0.188. `main` calls
  `ensureBinaryReady`, then `spawnInstalledBinary`; its env merges process.env
  and optional env and adds CODEBUFF_LAUNCHER_PID. That wrapper does not prove
  the Desktop UI input route. Do not launch/update it just to inspect.
- Desktop registry names version 0.0.182 and
  `C:/Users/vac34/AppData/Local/Programs/@codebufffreebuff-desktop/Freebuff.exe`.
  Its resources/app.asar contains real electron/main.cjs, preload.cjs,
  ipc-sender.cjs, orchestrator-request.cjs and launch-bootstrap.cjs. Exact
  SHA256-checked read-only extracts and archive identity are preserved in
  installed-source/ and installed-source-manifest.json.
- `electron/main.cjs` documents and implements Electron -> packaged Bun ->
  resources/orchestrator/orchestrator.js over local HTTP/SSE. resolveOrchestrator
  is at line 352; actual spawn/env at lines 712-762. Launch secrets are scrubbed
  from env and delivered through a stdin bootstrap, rather than an env token.
  This existing boundary must be understood before inventing another wrapper.
- The real installed orchestrator bundle is
  `C:/Users/vac34/AppData/Local/Programs/@codebufffreebuff-desktop/resources/orchestrator/orchestrator.js`
  (10,978,696 bytes). It retains source-path comments and function names.
  localApiDriverRoute at 166704 distinguishes a local driver; /api/threads and
  /api/thread/<id>/message are relevant. threadRoutes begins at 250869.
  runAgentStep at 123869 and run_terminal_command bindings around 213664 are
  additional route locators, not yet a verified complete call chain.

No Freebuff process was live in the process observation. No fresh Freebuff UI
event, host-to-engine carrier, FastPrompter T-1479 admission or GUI acceptance is
claimed. Do not substitute ZAICODE as the incident host. Do not invent the
FastPrompter checkout path: obtain it from actual host/project metadata.

## Next available work

Finish the exact Desktop input -> thread message -> engine/model -> shell tool
route in the actual source, recording file/symbol/line and generation. Inspect
host_authority_client.py, host_authority_broker.py and protocol_admission.py for
the existing authenticated host-event interface. Reproduce real carrier forgery
as a repository regression, then repair SAIPEN authority without broadening or
fabricating host privileges. Produce a separate Freebuff implementation handoff
with inspected symbols. Preserve the complete original mission and live gates.
Source/implementation mutations are still owed; this is SCOUT, not a fix claim.

Earlier work in this goal turn: T-1842 and T-1843 reached DONE in pending cohorts
C-016/C-017 (224 and 60 scoped tests respectively, no publication). T-1821's
local 158-test result is preserved; its three genuinely missing acceptance/
observation clauses remain BLOCKED, not waived. Current native source runtime
is C:/ProgramData/SAI/SAIPEN/python/3.11.9-64/python.exe; bin/saipen.cmd also
prepends that directory to PATH. Match that environment for native evidence.
