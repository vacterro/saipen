# T-2066 / SRC-417 — ZAICODE authenticated operator ingress repair

Status after BUILD + measurement on 2026-11-16. The reported incident
(SRC-390/SRC-415): a genuine operator `cc` under the real ZAICODE host was
refused at the prompt boundary, the origin never sealed, and the valve stayed
`hard_wait`. This ticket repairs the source defects; authorization to install
the rebuilt runtime and the live post-fix acceptance stay with T-2060.

## The five defects and their measured repairs

| # | defect | repair | control |
| --- | --- | --- | --- |
| 1 | `saipen/REGISTRY.json` shipped no `protocol_admission.host_authority.hosts` map, so host `"zaicode"` fell back to the Claude policy: the ZAICODE image was not a host image (`NOT_HOST_DESCENDANT`) | a measured `zaicode` per-host policy: images `zaicode.exe`/`ZCode.exe`, `max_shells: 0`, `max_bridges: 0` (`REGISTRY.json:1402`) | `PolicyTests` (3) — red on HEAD, green now |
| 2 | `host_authority_broker.py` spelled `int(host_cfg.get("max_shells") or 4)` / `("max_bridges") or 2`, so a declared zero became the shipped default and the host that execs its hook with `shell:false` could not declare "no shells" | `int_setting()` (`host_authority_broker.py:177`), used at `:726-727`: absent/unreadable keeps the default, an explicit zero is a value | `ZeroBoundTests` (2) plus the shell negative in `HostTests` |
| 3 | `host_authority_client.hook_invocation()` built one GLOBAL policy, carried no `bridge_images`/`max_shells`/`max_bridges`, and decided for `"zaicode"` under Claude's settings | per-candidate effective settings (`host_authority_client.py:266`), with the same bounds and bridges the broker will use; `identify_self()` answers a named host with ITS images (`:308`) | `ClientTests` (2) + `test_the_named_host_answers_with_its_own_images` |
| 4 | `operator_origin.OperatorOrigins._chain` required an observable birth time for EVERY ancestor. A protected Windows ancestor (wininit/services) hides it, so the whole chain was discarded and the broker answered `HOST_PROVENANCE_UNAVAILABLE: native host process birth could not be observed` for a genuine host delivery | keep the verified prefix and stop at the first ancestor the OS cannot measure (`operator_origin.py:89`); the caller's own birth and every retained link are still mandatory | `AncestryTests` (3) + both `HostTests` admission cases |
| 5 | end-to-end: nothing in the suite exercised a real ZAICODE-shaped process tree through the shipped hook, broker service and admission | `tools/test_t2066_zaicode_host_policy.py` — stand-in `zaicode.exe` host, installed shipped hook bytes, real `tools/authority_service.py`, four negative callers | red/green logs below |

## Measured facts this policy rests on

- Host image names, read from the running host tree and the ZAICODE desktop
  distribution: `zaicode.exe` (and the `ZCode.exe` spelling).
- Code signature: **the ZAICODE desktop build on this machine is NOT signed.**
  `Get-AuthenticodeSignature` on
  `_ZAICODE/zcode/packages/desktop/dist/win-unpacked/zaicode.exe` answers
  `NotSigned`, and `host_authority_process.image_signer` answers `None` for
  every running `zaicode.exe` ancestor (it answers `Python Software Foundation`
  for the interpreter). The previous SCOUT note claiming a DigiCert publisher
  was wrong; `host_signers: []` is therefore the measured decision, not an
  omission — a signer requirement would refuse the operator's own host.
  What binds the host instead: its name, the direct-parentage shape, the exact
  hook command line, the shipped hook bytes, and birth-time pid-reuse defence.
- The hook is started with `argv`, `shell:false` (no shell between host and
  hook), which is what makes `max_shells: 0` the honest bound.
- Windows ancestry from the broker's own process reaches protected system
  ancestors whose `created` is unreadable; that is defect 4's measured trigger.

## Measurements

| run | command | result |
| --- | --- | --- |
| RED (HEAD bytes for the three engine modules; registry hosts map present) | `pytest tools/test_t2066_zaicode_host_policy.py -q` | **7 failed, 8 passed** (`red-control.log`) |
| GREEN (repaired bytes, sha256 verified before/after) | same | **15 passed** (`green-run.log`) |
| NEIGHBORS | broker / origin / campaign / host-integration / ingress / freebuff / identity-diagnostics / profile-isolation families | **270 passed, 1 skipped, 163 subtests** (`neighbor-family.log`) |
| ZAICODE-specific family, modules run together | 10 modules incl. `test_t1859_zaicode_seal`, `test_t1868_zaicode_ingress`, `test_t1935_zaicode_hook_ownership` | 80 passed, 6 failed — **identical 6 fail on HEAD bytes** (`/tmp/head_zaicode_family.log`), i.e. pre-existing order-dependent pollution, not this change; every module passes alone |

The RED failures are the same oracle: missing per-host policy binding, the
explicit zero restored to 4/2, the client's global-policy decision, the
all-or-nothing ancestry, and the (absent) sealing path.

## Negative security regression (proved in `HostTests`)

| caller | outcome |
| --- | --- |
| host's own hook (argv, `shell:false`) | `sealed: true`, `authenticated: true`, `operator_origin` present, `seal.code: SEALED` |
| the same hook through a shell | not sealed; broker refuses `BROKER_CLIENT_NOT_AUTHENTICATED` — "too many shells between the hook and the host application" |
| the same hook through a shell tool (`true && …`) | not sealed |
| a model-issued command (this interpreter, no host above) | not sealed |
| an unrelated image named `bystander.exe` in the host's role | not sealed |

## VERIFY: canonical measured pair

`regression: required` was declared on the board, and the pair was executed by
the engine itself (`saipen work regression T-2066 --file
.saipen/evidence/T-2066/regression.json`), not attested in prose.

- **Contract:** `{python} -m pytest tools/test_t2066_zaicode_host_policy.py`
  (`format: pytest`, timeout 300 s). The executor stages the declared context
  into a temporary sandbox and runs BOTH halves there, so the context names
  every fixture input the tests read (`VERSION`, `saipen/`, `bootstrap/`,
  `extensions/adapters/`, `test_fixture_support.py` and the other helper
  modules). An undeclared input fails the run inside the sandbox even though
  the same test passes in the repository tree — that was measured twice before
  the context was complete.
- **Pre-fix material:** `git show HEAD:` bytes for
  `host_authority_broker.py`, `host_authority_client.py`, `operator_origin.py`,
  and the current `REGISTRY.json` with only the `hosts` map removed (the rest
  of that file's pending diff belongs to other tickets and is identical in
  both halves). Carriers live under `.saipen/evidence/T-2066/pre/`.
- **Measured runs:** before `exit 1`, 8 failed / 7 passed; after `exit 0`,
  15 passed. Recorded in
  `.saipen/evidence/regression/regression-execution-5a4171eb…json`
  (events E-21230 FAIL, E-21231 PASS). A second invocation
  (`…7778d2ff…json`, E-21232/E-21233) repeated the identical measurement after
  a capture-file misread; `log.regression_evidence` takes the latest FAIL and
  latest PASS of the cycle, and both executions carry the same verifier
  `548edc00835b3eb0…`, so the recorded verdict is
  **ADMISSIBLE — the same verifier failed against the pre-fix subject and
  passed against the post-fix subject** (subjects `91bb821f…` → `347d7e67…`).
- **Current-tree matrix:** `python -m pytest
  tools/test_t2066_zaicode_host_policy.py` → **15 passed in 3.02s**
  (`verify-run.log`).
- **Repository validation:** the named install's `saipen validate` reports
  `CURRENT_FAIL` with exactly two pre-existing core findings — EX-000052
  closure provenance drift (the installed engine generation moved) and
  FG-0046 naming slice ticket T-1936 which is not on BOARD. **No finding
  names T-2066.** A transient `cross_doc_drift [root-file-set]` finding was
  caused by this session's own mis-quoted shell redirect creating two scratch
  files at the repository root; the files were removed and the finding cleared.

Confidence: **high** — the pair is engine-measured, the negative callers are
real processes, and the neighbor family (270 passed, 1 skipped, 163 subtests)
is unchanged on the same tree.

## REVIEW: independent re-run and self-audit

- **Independent re-run:** the ticket verifier was run again on the current tree
  in REVIEW, not read from the VERIFY claim: **15 passed in 3.34s**
  (`review-run.log`).
- **Oracle check:** no existing test, fixture or verification command moved.
  The only verifier is the new `tools/test_t2066_zaicode_host_policy.py`, and
  its bytes are identical in both pair halves (the engine's verifier digest
  `548edc00835b3eb0…` is the same for the pre-fix and post-fix run). The
  pre-fix subject's red half is produced by this verifier: the named failure
  set is the five defects (policy absent, zero restored to defaults, global
  client decision, all-or-nothing ancestry, no sealing), not collection or
  import noise.
- **Owned-diff self-audit** (four modified files + one new test):
  - `int_setting` is called only with the two keys it defaults; `host_cfg` is
    always a dict at both call sites; a missing or unreadable value keeps the
    shipped default, an explicit zero survives.
  - `hook_invocation` rebuilds the config per candidate host; the no-host path
    keeps the old global answer. `identify_self(host=…)` now answers that
    host's images, which is the only in-tree caller shape (`authority_service`
    calls it without a host).
  - `_chain` callers were inspected: `register_worker` requires the proven
    host in the worker's ancestry and `_worker` looks up bindings along the
    chain. Truncation can only remove authority (fail-closed): a shorter chain
    can never register or reuse a worker bound above the truncation point. A
    caller whose own birth is unmeasurable still proves nothing.
  - The registry entry carries exactly the measured facts (names, rendered
    zero bounds, empty signers for an unsigned host); no other policy key
    reaches the ZAICODE host.
- **Findings:** none. No follow-up ticket is warranted from this delta.

## Not in this ticket

- Installing the rebuilt runtime into the live machine runtime and the live
  ZAICODE hook surface: that is SRC-415/T-2060, blocked on a fresh
  authenticated native operator carrier (`WAIT_USER_DECISION`).
- Therefore no post-fix live `cc` event exists yet; the seal is proven on the
  real process shape, not on a production delivery.
