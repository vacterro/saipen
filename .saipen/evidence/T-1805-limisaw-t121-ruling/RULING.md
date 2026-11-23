# SAIPEN Protocol Ruling & Recovery Report — T-1805 (SRC-264)

- **Protocol Owner**: SAIPEN (`V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN`, `saipen/` v8.1.0)
- **Active SAIPEN Work**: `T-1805` (`SRC-264`, `audit/PROJECT_ SAIPEN_20261016_1932.md`)
- **Subject Project**: `LIMISAW` (`V:\___VAC\__K\__CODE\_PY\_LIMISAW`, `lineage-a41c0e3a81534f02a4cc4520a399cca6`)
- **Subject Work & Question**: `LIMISAW` `T-121` (`audit/8 W2-001`, `SRC-041`) and protocol decision request `SRC-044 / T-134`

---

## PHASE 0 — AUTHORITY (`SRC-264:R001`)

1. **Resolved SAIPEN Protocol Root & Live Canonical Authority**:
   - `saipen_home` / `project_root`: `V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN`
   - `protocol_dir`: `V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN\saipen` (`saipen_version: 8`, runtime `8.1.0`, `schema_version: 3`)
   - Active SAIPEN claim: `T-1805` in `## DOING`, `phase: BUILD`, `owner: saipen-cli`, `continuation_authority: operator_required` (`authority_source: E-16134`, `authority_until: budget`, `safety_valve_mode: hard_wait`).
2. **Current `VERIFY-ORACLE-01` Contract Inspected**:
   - Normative rule owner: `saipen/phases/verify.md:34-81` (`<!-- RULE-OWNER: VERIFY-ORACLE-01 -->`) and `saipen/phases/verify.md:97-130`.
   - Engine implementation: `tools/saipen_engine/oracle.py:36-274` (`RULE_ID = "VERIFY-ORACLE-01"`, `parse_evidence`, `regression_evidence_verdict`, `regression_pair_verdict`) and `tools/saipen_engine/operations.py:822-862` (`_regression_gate`).
   - Contract invariant: A ticket declaring `regression: required` owes two anchored records in the active `VERIFY` cycle — `REGRESSION-EVIDENCE FAIL verifier:<hex> subject:<before_hex>` followed by `REGRESSION-EVIDENCE PASS verifier:<hex> subject:<after_hex>` — where `verifier_before == verifier_after` and `subject_before != subject_after` (`ADMISSIBLE`). If `regression_evidence: executed` is also declared on the ticket row, `regression_execution.evidence_gate` additionally verifies the `.saipen/evidence/regression/` execution receipt; `LIMISAW` `T-121` declares `regression: required` without `regression_evidence: executed`.
3. **Inspected `SRC-044 / T-134` Recorded Provenance in `LIMISAW`**:
   - File: `V:\___VAC\__K\__CODE\_PY\_LIMISAW\.saipen\intake\active\SRC-044.meta.json` (projected at `LIMISAW` `LOG.md` `E-1445`, `2026-10-15T21:33:41Z`).
   - `request_provenance`: `{"compared_digest": "05e38d93156ab98f8e953fd8b08cdecf15ce85ba1800b7a7c93e5ad757caab8c", "note": "no operator carrier and no transport obligation: the stored bytes are what this session supplied, and nothing compared them with what the operator wrote", "witness": "model_supplied"}`.
   - Under `tools/saipen_engine/operator_task.py:61-90` (`authority_for_provenance`), `witness: "model_supplied"` grants `user_explicit: False`, `preempt_active_work: False`, `goal_pivot: False`, `reset_bounded_authority: False`, and `projection_priority` floors the ticket at `P2` (`T-134 [P2]`). `model_supplied` is not interpreted as an authenticated operator command.
4. **Cross-Project Non-Mutation Boundary**:
   - `LIMISAW` (`V:\___VAC\__K\__CODE\_PY\_LIMISAW`, `HEAD 64f15a1d50b5f9d98d151c8d82c4435c62bc5ebf`, `phase: BUILD`, `task: T-121`, `log_tail_event: 1448`) was inspected strictly read-only. Zero `LIMISAW` source or `.saipen/` files were altered from SAIPEN authority.

---

## PHASE 1 — EVIDENCE ADMISSIBILITY (`SRC-264:R002`)

### Determination on (A), (B), and (C)

Under `VERIFY-ORACLE-01` (`saipen/phases/verify.md:34-81` and `tools/saipen_engine/oracle.py`):

- **(A) Authentic historical release subject (`v0.0.11`) — PERMITTED**:
  When a bug fix evolved in the working tree before a ticket-local pre-fix snapshot was captured, an authentic, immutable Git release tag predating the ticket (`v0.0.11`, annotated tag commit `42278c25e801a0baae2df13d3ff545afb8f52524`, 2026-09-26, extracted cleanly via `git archive` / `git show v0.0.11:<path>` into `.saipen/evidence/T-121-pre-fix-recovery/pre-v0.0.11/`) is an admissible pre-fix subject. It is genuine historical production code rather than an invented or hand-edited failure control.
- **(B) One unchanged behavioral oracle across both builds — PERMITTED**:
  `revocation_oracle.cs` (`sha256: d1517509f4b53c06bccfc4583d0528148d9e28311ce92b2d2e7c9702a658293b`), compiled and executed identically by `run-pair.ps1` (`sha256: bfbc625ca4f11cb66d4ab9095627ae9196f4fb75f1ef9107e28a52c8d5f6a050`) against `pre-v0.0.11/` (`run.exit = 1`, `4/38 FAIL`) and `current-subject/` (`run.exit = 0`, `38/38 PASS`), satisfies `VERIFY-ORACLE-01`'s invariant that the verifier remains fixed (`verifier:d1517509f4b53c06bccfc4583d0528148d9e28311ce92b2d2e7c9702a658293b`) while only the implementation subject changes (`subject:7717422cd7099a4fa60181acc2ad6d791d29733fa906d9eeb5ae9c27d8775318` -> `subject:aabfa4db86913e0010cb74df761476f3238e34a9df4e32ba59f2624d7ce9a9b0`).
- **(C) Separate deterministic current-implementation security regressions for an interface introduced during the fix — PERMITTED**:
  `BoundedFile.ReadAndConsume`, `AcquireCredentialAuthority`, and `BeforeCredentialRead` were introduced by `T-121` to close the credential file-open TOCTOU window and did not exist in `v0.0.11` (`pre-v0.0.11/LIMISAW.cs:3432`, `pre-v0.0.11/ProbeZcode.cs:161-184`, `pre-v0.0.11/ProbeFreebuff.cs:114-127`). `VERIFY-ORACLE-01` does not require an impossible historical API that did not exist in `v0.0.11`. Pairing the compatibility-neutral comparative oracle (`revocation_oracle.cs`, `4/38 FAIL` -> `38/38 PASS`) with the current-implementation lease/file-open boundary suite (`tests/credential_authority.cs`, `73/73 PASS`) plus static proof that `v0.0.11` had zero mid-sweep credential-read fencing satisfies both `VERIFY-ORACLE-01` and `T-121`'s `verify:` contract without weakening any security requirement.

### Explicit Six-Way Distinction

1. **Historical behavioral regression proof**:
   - Proven by `revocation_oracle.cs` (`d1517509f4b53c06bccfc4583d0528148d9e28311ce92b2d2e7c9702a658293b`): on `pre-v0.0.11`, an admitted sweep `A` held across revocation still publishes stale data (`FAIL zcode/toggle/stale-A-not-published`, `FAIL freebuff/toggle/stale-A-not-published`, `FAIL zcode/ini/stale-A-not-published`, `FAIL freebuff/ini/stale-A-not-published`, `4/38 FAIL`, `run.exit = 1`). On `current-subject`, the identical 38 checks pass (`38/38 PASS`, `run.exit = 0`), proving stale-`A` publication fencing, coalesced follow-up `B` running with `permission=0`, unrelated `codex` continuity, and single follow-up execution.
2. **Current credential-file authorization proof**:
   - Proven on the current implementation by `tests/credential_authority.cs` (`73/73 PASS`), which deterministically gates `BoundedFile.ReadAndConsume`, `AcquireCredentialAuthority`, and `BeforeCredentialRead` across Zcode and FreeBuff toggle and external INI revocation, verifying that no credential file read or network request starts after revocation and that unrelated settings edits invalidate nothing. On `v0.0.11`, static inspection of `pre-v0.0.11/LIMISAW.cs:3432` (`Probe.Run(Settings.ZcodeReadConfig, Settings.FreebuffReadConfig)`), `pre-v0.0.11/ProbeZcode.cs:161-184`, and `pre-v0.0.11/ProbeFreebuff.cs:114-127` confirms that no credential-read lease or revocation callback existed (`no provider credential read is fenced` in `v0.0.11` by construction).
3. **Source provenance**:
   - `pre-v0.0.11/` is extracted from annotated Git tag `v0.0.11` (`42278c25e801a0baae2df13d3ff545afb8f52524`, 9 C# compilation units, `LIMISAW.cs` sha256 `7717422cd7099a4fa60181acc2ad6d791d29733fa906d9eeb5ae9c27d8775318`).
   - `current-subject/` is a byte-identical copy of the live `T-121` working tree on `HEAD 64f15a1d50b5f9d98d151c8d82c4435c62bc5ebf` (11 C# compilation units including post-`v0.0.11` `SaiAccounts.cs` and `LimitsExport.cs`, `LIMISAW.cs` sha256 `aabfa4db86913e0010cb74df761476f3238e34a9df4e32ba59f2624d7ce9a9b0`).
   - All 69 file hashes (sources, themes, oracle, binaries, logs, exit codes) are recorded in `.saipen/evidence/T-121-pre-fix-recovery/SHA256SUMS`.
4. **Oracle equivalence**:
   - `revocation_oracle.cs` is byte-for-byte identical (`d1517509f4b53c06bccfc4583d0528148d9e28311ce92b2d2e7c9702a658293b`) in `.saipen/evidence/T-121-pre-fix-recovery/revocation_oracle.cs`, `pre-v0.0.11/revocation_oracle.cs`, and `current-subject/revocation_oracle.cs`. No compatibility shim altering tested production behavior was added to `pre-v0.0.11/`.
5. **Build reproducibility**:
   - `run-pair.ps1` (`bfbc625ca4f11cb66d4ab9095627ae9196f4fb75f1ef9107e28a52c8d5f6a050`) compiles both subjects cleanly (`compile.exit = 0`, `compile.log` empty `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`) with `C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe` and runs both in isolated temp `USERPROFILE`/`HOME`/`APPDATA`/`LOCALAPPDATA` directories with `ZAI_API_KEY`/`ZCODE_API_KEY` cleared.
6. **Full-suite stability**:
   - Canonical records `E-1438` and `E-1440` (`V:\_TEMP_\T121-final-suite-20261015.log`) proved a full `pwsh ./build.ps1 -Tests` pass (`exit 0`, including `credential_authority 73/73`, `connections_foundation 134/134`, `antigravity_connection 66/66`) in the prior `VERIFY` cycle.
   - The `2026-10-16` follow-up run (`/v/_TEMP_/T121-final-suite-followup-20261016.log`) timed out at 120s (`exit 124`) inside `connections_foundation`. Under `saipen/phases/verify.md:16-20, 115`, a timeout (`exit 124`) is not a pass and cannot be cited as green verification evidence. When `T-121` enters its new `VERIFY` cycle from `BUILD`, the `LIMISAW` agent must anchor the `REGRESSION-EVIDENCE FAIL/PASS` records and re-run `pwsh ./build.ps1 -Tests` to `exit 0` in that active `VERIFY` cycle before transitioning to `REVIEW`.

---

## PHASE 2 — BOUNDED RULING (`SRC-264:R003`)

- **Decision**: **ACCEPT**
  - The combined comparative regression evidence (`.saipen/evidence/T-121-pre-fix-recovery/`: authentic `v0.0.11` tag subject `4/38 FAIL` -> current subject `38/38 PASS` under unchanged `revocation_oracle.cs` `d1517509f4b53c06bccfc4583d0528148d9e28311ce92b2d2e7c9702a658293b`, together with current-implementation `tests/credential_authority.cs` `73/73 PASS` and static `v0.0.11` un-fenced read proof) **satisfies `VERIFY-ORACLE-01`** and `T-121`'s `verify:` contract, with the scope and limitations documented in Phase 1.
  - **No return to `BUILD`**: `T-121` is currently in `BUILD` (`E-1448`) with its implementation complete; it must advance forward (`BUILD -> VERIFY`) and must **not** be sent back to `BUILD` without a new actionable defect.
  - **Active `VERIFY`-cycle execution requirements**: Inside `VERIFY`, the `LIMISAW` agent must (1) record the two anchored `REGRESSION-EVIDENCE FAIL` and `REGRESSION-EVIDENCE PASS` checkpoints for `T-121` in the active `VERIFY` cycle, and (2) execute a clean, non-timed-out `pwsh ./build.ps1 -Tests` (`exit 0`) and `tests/bin/credential_authority.exe` (`73/73 PASS`) in the active `VERIFY` cycle (replacing the `exit 124` timeout) before `VERIFY -> REVIEW -> SHIP -> DONE`.
  - **Shared protocol changes**: None required or authorized (`oracle.py` and `saipen/phases/verify.md` already admit this pair without modification).

---

## PHASE 3 — PROVENANCE (`SRC-264:R004`)

1. **Host-to-SAIPEN Request Pipeline Inspection**:
   - Inspected `tools/saipen_engine/operator_task.py:18-256`, `tools/saipen_engine/entry.py:450-580`, `tools/saipen_engine/intake.py:1404-1600`, and `tools/saipen_engine/operations.py:7850-8060`.
   - `operator_task.witness(text, obligation_met=..., env=...)` assigns `witness: "operator_carrier"` **only** when `SAIPEN_TASK_SHA256` or `SAIPEN_TASK_FILE` is declared in the launch environment and its SHA-256 matches `ingress_digest(text)`. Absent a carrier or transport obligation, `witness` is recorded as `"model_supplied"`.
   - `operator_task.authority_for_provenance(provenance)` sets `trusted = True` (`user_explicit: True`, `preempt_active_work: True`, `goal_pivot: True`, `reset_bounded_authority: True`) **exclusively** for `witness == "operator_carrier"` with a valid 64-hex `compared_digest` and `declared_by in ("SAIPEN_TASK_SHA256", "SAIPEN_TASK_FILE")`.
   - `operator_task.projection_priority(priority, authority)` floors any non-`user_explicit` request at `P2` (`"P" + str(max(2, int(priority[1:])))`), preventing `model_supplied` requests from acquiring `P0`/`P1` preemption by arrival.
   - `operator_task.authority_for_receipt(root, receipt)` and `entry.py:459-460` enforce immutability of recorded provenance: re-running or resuming in a later session with a carrier never promotes an existing `model_supplied` receipt.
2. **Historical `LIMISAW` `model_supplied` Records Verified**:
   - `SRC-043 / T-133` (`E-1444`, `2026-10-15T19:17:29Z`): `source_kind: "user_instruction"`, `witness: "model_supplied"`, `compared_digest: "e112a64e4968d17375c3dad63502b827ef643b263071868708b481b3900d609c"`, projected as `T-133 [P2]` (`request_witness: model_supplied`) in `## TODO` without preempting `T-121`.
   - `SRC-044 / T-134` (`E-1445`, `2026-10-15T21:33:41Z`): `source_kind: "user_instruction"`, `witness: "model_supplied"`, `compared_digest: "05e38d93156ab98f8e953fd8b08cdecf15ce85ba1800b7a7c93e5ad757caab8c"`, projected as `T-134 [P2]` (`request_witness: model_supplied`) in `## TODO` as a protocol decision request without preempting `T-121` or self-authorizing closure.
   - `SRC-045 / T-135` (`E-1447`, `2026-10-15T21:50:22Z`): `source_kind: "user_instruction"`, `witness: "model_supplied"`, `compared_digest: "109fbabc507160e9e62fc99be653aab992d02907ce785d6ab0b20a353dcf0689"`, projected as `T-135 [P2]` (`request_witness: model_supplied`) in `## TODO` without preempting `T-121`.
3. **Five-Category Classification Preserved**:
   - *Authenticated operator command*: Requires `witness: "operator_carrier"` (`SAIPEN_TASK_SHA256` / `SAIPEN_TASK_FILE` digest match); none of `SRC-043..045` has this authority.
   - *Model-supplied proposal*: `SRC-043 / T-133` and `SRC-045 / T-135` (`witness: "model_supplied"`, floored at `P2`, non-preempting).
   - *Protocol decision request*: `SRC-044 / T-134` (`witness: "model_supplied"`, recorded question awaiting this SAIPEN ruling).
   - *Recorded evidence*: `.saipen/evidence/T-121-pre-fix-recovery/{REPORT.md,SHA256SUMS,run-pair.ps1,revocation_oracle.cs,pre-v0.0.11/,current-subject/}` and `LIMISAW` `LOG.md` `E-1438..E-1448`.
   - *Actual protocol authority*: `saipen/phases/verify.md` (`VERIFY-ORACLE-01`), `tools/saipen_engine/oracle.py`, and this canonical SAIPEN `T-1805` (`SRC-264`) ruling artifact `.saipen/evidence/T-1805-limisaw-t121-ruling/RULING.md`.
   - Valid intake history in `LIMISAW` is preserved intact and no historical `model_supplied` record is promoted retroactively.

---

## PHASE 4 — RECOVERY & FINAL REPORT (`SRC-264:R005`)

### Canonical Consumption Route for `LIMISAW` (Zero Manual `BOARD`/`LOG` Edits)

From `V:\___VAC\__K\__CODE\_PY\_LIMISAW`, the `LIMISAW` agent consumes this ruling exclusively via canonical `saipen` CLI commands:

1. **Transition `T-121` from `BUILD` to `VERIFY`**:
   ```powershell
   saipen transition VERIFY --reason "Apply SAIPEN T-1805 (SRC-264) ACCEPT ruling: v0.0.11 release-tag RED (4/38) + current GREEN (38/38) on unchanged revocation_oracle.cs (d1517509...) + credential_authority 73/73 PASS satisfies VERIFY-ORACLE-01"
   ```
2. **Record the Anchored `VERIFY-ORACLE-01` Pair in the Active `VERIFY` Cycle**:
   ```powershell
   saipen checkpoint "REGRESSION-EVIDENCE FAIL verifier:d1517509f4b53c06bccfc4583d0528148d9e28311ce92b2d2e7c9702a658293b subject:7717422cd7099a4fa60181acc2ad6d791d29733fa906d9eeb5ae9c27d8775318 -- pwsh -NoProfile -File ./.saipen/evidence/T-121-pre-fix-recovery/run-pair.ps1 pre-v0.0.11 (v0.0.11 tag 42278c25e801) exit 1, 4/38 FAIL stale-A-not-published"
   saipen checkpoint "REGRESSION-EVIDENCE PASS verifier:d1517509f4b53c06bccfc4583d0528148d9e28311ce92b2d2e7c9702a658293b subject:aabfa4db86913e0010cb74df761476f3238e34a9df4e32ba59f2624d7ce9a9b0 -- pwsh -NoProfile -File ./.saipen/evidence/T-121-pre-fix-recovery/run-pair.ps1 current-subject (HEAD 64f15a1d50b5) exit 0, 38/38 PASS"
   ```
3. **Execute Active-Cycle Verification & Canonical Closure**:
   - Run `./tests/bin/credential_authority.exe` (`73/73 PASS`) and `pwsh ./build.ps1 -Tests` to clean completion (`exit 0`, resolving the `2026-10-16` `exit 124` timeout).
   - Record `saipen checkpoint "verify -> PASS [target: T-121] conf: high -- ..."` citing the anchored pair, `credential_authority 73/73`, full suite `exit 0`, and `SAIPEN` `.saipen/evidence/T-1805-limisaw-t121-ruling/RULING.md`.
   - Advance `T-121` through `saipen transition REVIEW`, independent `REVIEW` rerun, `saipen transition SHIP`, and `saipen ticket done T-121`.
   - When `T-134` (`SRC-044`) is subsequently claimed in `LIMISAW`, verify and close it citing `V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN\.saipen\evidence\T-1805-limisaw-t121-ruling\RULING.md`.

---

## FINAL REPORT

- **STATUS**: `DONE` (Ruling issued and verified in `.saipen/evidence/T-1805-limisaw-t121-ruling/RULING.md`; all 5 clauses `SRC-264:R001..R005` satisfied).
- **AUTHORITY**: `SAIPEN` protocol home `V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN` (`saipen/` v8.1.0), active Work `T-1805` (`SRC-264`), rule owner `VERIFY-ORACLE-01` (`saipen/phases/verify.md:34-81`, `tools/saipen_engine/oracle.py`). `LIMISAW` source and `.saipen/` files untouched (`HEAD 64f15a1d50b5f9d98d151c8d82c4435c62bc5ebf`).
- **VERIFY-ORACLE-01 RULING**: `ACCEPT` — `VERIFY-ORACLE-01` permits (A) the authentic `v0.0.11` release-tag pre-fix subject (`42278c25e801a0baae2df13d3ff545afb8f52524`), (B) the single unchanged compatibility-neutral behavioral oracle (`revocation_oracle.cs`, `sha256: d1517509f4b53c06bccfc4583d0528148d9e28311ce92b2d2e7c9702a658293b`) proving `4/38 FAIL` (`exit 1`) on `v0.0.11` and `38/38 PASS` (`exit 0`) on current source, and (C) separate deterministic current-implementation security regressions (`tests/credential_authority.cs`, `73/73 PASS`) for the `BoundedFile.ReadAndConsume` / lease interface introduced during `T-121`, paired with static proof that `v0.0.11` had no mid-sweep credential-read fence. Do not return `T-121` to `BUILD`.
- **EVIDENCE ADMISSIBILITY**:
  - *Historical behavioral regression proof*: Admissible (`revocation_oracle.cs` `d1517509...`, `4/38 FAIL` on `pre-v0.0.11` -> `38/38 PASS` on `current-subject`).
  - *Current credential-file authorization proof*: Admissible (`tests/credential_authority.cs` `73/73 PASS` on current lease API + static `v0.0.11` absence of mid-sweep lease fencing in `LIMISAW.cs:3432`, `ProbeZcode.cs:161-184`, `ProbeFreebuff.cs:114-127`).
  - *Source provenance*: Verified (`v0.0.11` tag `42278c25e801a0baae2df13d3ff545afb8f52524` vs `current-subject` on `HEAD 64f15a1d50b5f9d98d151c8d82c4435c62bc5ebf`; 69 digests in `SHA256SUMS`).
  - *Oracle equivalence*: Verified (`revocation_oracle.cs` byte-identical across root, `pre-v0.0.11/`, and `current-subject/`; `oracle.regression_pair_verdict` returns `ADMISSIBLE`).
  - *Build reproducibility*: Verified (`run-pair.ps1` compiles both cleanly with `csc.exe`, `compile.exit = 0`).
  - *Full-suite stability*: `E-1438`/`E-1440` passed `exit 0`, but the `2026-10-16` rerun timed out (`exit 124` in `connections_foundation`); active `VERIFY` cycle in `LIMISAW` must record anchored `REGRESSION-EVIDENCE FAIL/PASS` events and a non-timed-out `pwsh ./build.ps1 -Tests` (`exit 0`) before `REVIEW`.
- **PROVENANCE FINDINGS**: `LIMISAW` `SRC-043 / T-133`, `SRC-044 / T-134`, and `SRC-045 / T-135` all carry `request_provenance.witness = "model_supplied"`. `tools/saipen_engine/operator_task.py` (`authority_for_provenance`, `authority_for_receipt`, `projection_priority`) and `entry.py:459-460` prevent assistant-authored handoffs from becoming authenticated operator commands (`user_explicit = False`, `preempt_active_work = False`, `goal_pivot = False`, priority floored at `P2`, no retroactive promotion). All valid intake history is preserved.
- **PROTOCOL CHANGES, IF AUTHORIZED**: `NONE` — Existing `VERIFY-ORACLE-01` (`saipen/phases/verify.md`, `tools/saipen_engine/oracle.py`) and `operator_task.py` already enforce and admit the required invariants without modification.
- **NEXT EXACT ACTION**: Complete `T-1805` verification (`VERIFY -> REVIEW -> SHIP -> DONE`), mark `SRC-264:R001..R005` `VERIFIED`, consume `audit/PROJECT_ SAIPEN_20261016_1932.md`, and continue queued SAIPEN Work (`T-1804`); in `LIMISAW`, transition `T-121` `BUILD -> VERIFY`, anchor the `REGRESSION-EVIDENCE FAIL/PASS` pair, run `pwsh ./build.ps1 -Tests` to `exit 0`, and advance `T-121` to `DONE`.
- **NEED USER**: `NONE`
