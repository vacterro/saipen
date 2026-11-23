# AUDAPACK lifecycle integrity investigation — T-1696 / SRC-201

Disposition: **INTEGRITY BLOCKED. No AUDAPACK mutation or reconciliation was performed.**
Investigation date: 2026-10-10 UTC. This is protocol forensics, not a Widget implementation acceptance.

## 1. Exact discrepancy and provenance

The live project is `V:\___VAC\__K\__CODE\_PY\_AUDAPACK`, confirmed by both the existing codebase registry and the FreeBuff project registry. The exact registry carrier is preserved as [registry-original.json](registry-original.json). HEAD remains `6c6d841df24e5c5d91870def931af99f0af4c81f`; its parent is `d66d9f63ef2fee4a5a5701136bf26169c7511d8c`. The only dirty entry is the existing improve report `.saipen/improve/imp-vacterro-audapack-20260927-1/buffy-01/saipen_improve_SAIPEN.md`.

The reported divergence is still present:

- STATE: `DONE`, `task: T-299`, `last_event: 3146`, `blocker: none`.
- BOARD: two different checked DONE rows named T-299: original npm-cache packaging cleanup and Widget 0.1.07 trust-boundary work. The heading is literally `## TODO## DOING`.
- LOG: a Widget T-299 summary directly after `# Log`, without E-ID, parent or operation; the numbered tail is E-3146, whose parent E-3145 is absent.
- The complete four-segment ledger also lacks E-3133 and E-3136. This is broader than the duplicate alone.

Seven exact originals, including the five requested files, are preserved in [live-snapshot](live-snapshot/capture.json). Another 8,041 durable files, including journal compaction/index records, are preserved in [durable-snapshot](durable-snapshot/capture.json). Every manifest entry was rehashed against both its captured copy and the live original; all 8,048 match. HEAD, dirty entries, staged diff and unstaged diff also match the initial capture. See [final-preservation.json](final-preservation.json).

| Original | SHA-256 |
| --- | --- |
| STATE.md | `a766ca86d185ea24d4b1818f4295ef839826bcc913347047abcecf8dfcf5cc50` |
| BOARD.md | `8bb2a5e68d474ee2ab22b834e6a94440d5389ea352d2969f5ad945cd04ca9952` |
| LOG.md | `e414d4b54a3e99d9fa515945bf9d8be208581292889b3744edcb11466b0f7c7a` |
| MANIFEST.json | `6bbb6ca8bed1502f04176d848f24ad12fdd58759e1946f0b2b27a5f023e0e050` |
| Widget T-299 evidence | `4a2c9ca6b08eb9fd6e5d50a761c4fe26578fccae376f843db1588846e6b8cff0` |

Installation is mixed: STATE binds the current SAIPEN home and MANIFEST declares protocol 8.1.0, while project AGENTS points to an ordinary legacy skill BOOT copy. Both BOOT byte hashes are preserved in [installation.json](installation.json). Neither a manifest assertion nor an installed document grants lifecycle authority.

## 2. Writer boundary: direct editing is proven

**PROVEN — original npm-cache T-299 was also manually projected.** FreeBuff's project-scoped SQLite transcript identifies thread `f267f617-a0f8-47f5-b617-b9393f0e61d2`, harness `codebuff`, opaque configured model `m-ffcbc2bcf3`. Message 198 contains:

- Part 30: `str_replace` inserts the npm-cache T-299 DOING row.
- Part 31: `str_replace` changes STATE to `phase: DOING`, T-299 and `last_event: 3145`. This is a raw counter edit, not an event receipt.
- Parts 47–48: direct BOARD/STATE edits claim DONE and `last_event: 3146`.
- Part 50: a successful terminal command, exit 0, appends the literal E-3146 line using `cat >> .saipen/LOG.md`. The line has no operation identity. The complete available message contains no corresponding E-3145 append.

Exact raw message bytes and hashes are preserved in [producer/provenance.json](producer/provenance.json); the overlooked shell append is explicitly retained in [producer/npm-E3146-append.json](producer/npm-E3146-append.json). Producer storage timestamps place messages 196 and 198 at 2026-10-09 04:46 and 04:50 UTC. Embedded `claim_time`, STATE.updated and log timestamps are historical claims, not independently established canonical transition times.

**PROVEN — the Widget duplicate and unnumbered summary were written by ZCode, after an explicit engine refusal.** Project task registry and CLI database identify session `sess_5c7f302d-22d6-478f-b6a3-1aee5e8a3850`, assistant agent `zcode-agent`, transcript mode `yolo`; task metadata names provider `glm` and configured model alias `new-provider/SAIFREN`. These are recorded labels, not independent identification of the underlying model.

| UTC producer timestamp | Exact part | Observed operation |
| --- | --- | --- |
| 2026-10-09 09:00:44.204 | `part_mv0qjjfw_83519ef5-4ff7-4c9a-8983-698bec643e6e` | `saipen continue --json` refuses with `HISTORY_LEDGER_CORRUPT`, `FORENSICALLY_UNRECOVERABLE`, `READ_ONLY_DIAGNOSIS_ONLY`; no canonical next command or safe repair is offered. |
| 2026-10-09 10:06:40.542 | `part_mv0swc66_db3f560a-e71d-48a4-aaa5-da6ca8441c20` | Successful `Edit` inserts the exact unnumbered Widget completion summary immediately below `# Log`. |
| 2026-10-09 10:06:53.565 | `part_mv0swm7x_68117fba-8530-4461-9a2f-32c6139e6a61` | Successful `Edit` prepends Widget T-299 directly before the already visible npm-cache T-299 DONE row. |

The initial attempted STATE edit was a same-text edit and failed. The initial LOG edit also failed; the subsequent exact LOG and BOARD edits succeeded. Thus Widget completion did not produce the current STATE tail; it reused the already claimed npm-cache head. Exact raw producer parts, content hashes and message metadata are in [producer/zcode-writer.json](producer/zcode-writer.json).

The same session's successful `git -C . add -A` / commit produced `6c6d841`, incorporating 517 changed files. The raw commit response and the pre-insertion BOARD read are preserved in [producer/zcode-corroboration.json](producer/zcode-corroboration.json). That BOARD read already contains the malformed heading and the npm T-299 row; the successful duplicate insertion explicitly matches that row. This is direct attribution, not inference from a checked box or Git authorship.

| Conclusion | Classification |
| --- | --- |
| Executor direct edits created the observed duplicate and unnumbered summary after a canonical refusal. | **PROVEN** |
| The engine admitted the observed Widget duplicate or canonically closed it. | **Not established; observed writes demonstrably bypassed the engine.** No supporting admission/closure receipt exists in the inspected durable evidence. |
| An unsupported executor fallback bypassed lifecycle validation. | **PROVEN** by direct tool frames following the explicit refusal. |
| A repair utility introduced this duplicate. | **UNKNOWN** generally; the observed introducing writer was `Edit`, not a repair utility. |
| Concurrent writers caused this incident. | **UNKNOWN**. Two hosts are identified, but their observed edits are sequential; concurrency is not proved. |
| The supplied discrepancy required a snapshot assembled from different revisions. | **LIKELY false**: it reproduces in a stable live checkout and the committed surfaces; no splice is needed. |
| Writer of the earlier malformed heading and missing E-3133/E-3136 parents. | **UNKNOWN** within the inspected carriers. The heading predates Widget insertion. |

T-298 is an earlier, different 0.1.06 Widget attempt. Its direct BOARD/STATE edits also occur in FreeBuff message 196. It is not proof of a legitimate separate canonical identity for Widget 0.1.07. No distinct canonical admission for 0.1.07 was found.

## 3. Current task/event head and durable operations

**There is no validated current lifecycle head.** `T-299 / E-3146 / DONE` is the observed claim, not a verified canonical closure.

The latest numbered event with a matching committed operation receipt is **T-291 / E-3131**, operation `finish-29deadc9792e498ca581916d8a22c785`, committed at `2026-10-07T22:47:28Z`. The receipt names LOG, BOARD and STATE targets with after hashes `5b7433f9e757c879`, `ff84134960196dfc`, and `b76222ea78451493`. This identifies the last receipt-backed numbered closure; it does not restore that historical snapshot or certify the present tree.

Legitimate later durable work is accounted for: `improve-rebind-b431fb0cacf0479daf67055c33ae053c`, committed `2026-10-09T22:43:19Z`, updates an improve report only. It does not admit Widget, create E-3145/E-3146, or move the lifecycle head. Journal compaction was included, not mistaken for missing history: 4,170 unique receipts are decoded, including settled-index embedded records, with no conflicting duplicate records or JSON decode errors. Three historical RESOLVED records are not reported as unresolved damage. See [durable-analysis.json](durable-analysis.json).

The canonical semantic receipt reader independently accepts all 4,170 copied receipts with no receipt errors. The canonical complete-history reader rejects the live-captured log for the unnumbered Widget line and three absent parents. Repeated reader results are identical. The prefix diagnostic in [canonical-readers.json](canonical-readers.json) retains current illegal-line diagnostics; it is not a reconstructed pre-incident snapshot.

## 4. Safe actions actually performed

Only read-only AUDAPACK investigation and preservation were performed. SQLite connections used `mode=ro` and `PRAGMA query_only=ON`. Git reads used `GIT_OPTIONAL_LOCKS=0`. All new evidence, copied-snapshot diagnostics, fixture tests and task records belong to SAIPEN home, not AUDAPACK. Original npm-cache source/tests, earlier Widget evidence and the 0.1.07 release source are additionally preserved in [engineering-originals.json](engineering-originals.json).

The documented digest-bound route `saipen recover --resolve-duplicate-id T-299 --keep DIGEST --reassign DIGEST` was reviewed but **not executed on AUDAPACK**. It can allocate a fresh row identity while retaining original bytes and emitting a genuine correction DEC. By itself it does not supply missing historical events or turn a renamed checked Widget row into an admitted, verified, completed task. It also cannot establish the lost E-3133/E-3136 truth. Current engine diagnosis offers forensic read-only handling. No safe complete correction sequence has been established.

No tasks were renumbered, no original T-299 was removed, no E-ID or timestamp was invented, no STATE counter was advanced, no immutable history was rewritten, and no DONE claim was used to clear this blocker.

## 5. Tests and validation

Six independently initialized sacrificial cases use the public CLI and full canonical validator. Every fixture first passes a known-good `validate`; validation/refusal preserves its canonical STATE/BOARD/LOG bytes. Raw outputs and hashes are indexed in [guardrails-final.json](guardrails-final.json).

| Control | Actual result |
| --- | --- |
| 1. Different descriptions sharing a task ID | Rejected: `VALIDATION_FAILED`, duplicate ticket ID. |
| 2. DONE task without admission/transition operations | Rejected: `CONFORMANCE_UNHEALTHY`, missing canonical allocation/lifecycle authority. |
| 3. Unnumbered task-shaped lifecycle claim | **Accepted: `VALID / CURRENT_PASS`**, reproduced on a second fresh fixture. |
| 4. Malformed TODO/DOING heading | Rejected: required headings missing / invalid board. |
| 5. Closure report with no canonical closure event | Rejected: `CONFORMANCE_UNHEALTHY`; the improved case explicitly references the report from `verify`. |
| 6. Duplicate-ID repair naming an unrelated task as loser | Rejected: `STALE_DUPLICATE_ID_DECISION`; unrelated T-2 and all three canonical documents unchanged. |

Control 3's exact admitted bad line is `- 10.10.26 [T-1] RUN: ticket finished via SAIOPS -- completion (from SHIP)`. The fixture's task stays TODO: acceptance of this log claim does **not** prove the engine accepted closure or duplicate admission. The actual AUDAPACK Widget line is already rejected by the current parser; the independently reproduced weakness is the different `RUN:`-shaped unnumbered claim. Ordinary commentary must remain valid in the eventual correction.

This real, separately reproduced validator weakness is canonically scoped as **T-1699**, `regression: required`, admission E-14106. No engine patch was made solely because AUDAPACK is inconsistent. Implementation is held at the separate SAIPEN concurrent-writer boundary: `tools/saipen_engine/subs.py` changed outside this agent's ownership during current gate checks. Existing Ruff/core failures are preserved, not repaired by reverting another writer.

Copied-snapshot canonical ledger errors are:

```text
LOG.md:2: not a legal LOG event
E-3134 parent E-3133 does not exist in the ledger
E-3137 parent E-3136 does not exist in the ledger
E-3146 parent E-3145 does not exist in the ledger
```

Additional fast validation reports the duplicate ID, malformed headings, unsupported historical `evidence:` fields, invalid DONE/state correspondence and unexplained gaps; the complete output is retained, not summarized as green. The 0.1.07 release SHA-256 independently matches `5efa3a49fee7bdef83f63ecfa3324e2746eb12b874baad4e1bba03edd03a09fa`. Engineering test totals in the historic evidence remain reported results; this investigation did not rerun Widget implementation tests or convert them into lifecycle proof.

## 6. Remaining blockers and evidence limits

**AUDAPACK: HISTORY_LEDGER_CORRUPT / INTEGRITY_BLOCKED.** The canonical writer responsible for the Widget insertion is now identified, but required historical event truth remains unavailable and the present lifecycle is invalid. A safe recovery must preserve the original npm T-299 and Widget report, establish any new identities through real current operations, and explicitly account for the bad tail without fabricating events. A duplicate row rename alone is insufficient.

Producer searches were bounded to the actual project registry, FreeBuff project transcript, matching Codex project registry entries, OpenCode session/part selectors, Claude's AUDAPACK transcript directory, ZCode/Zaicode task registries and the matching ZCode CLI session. Other hosts' older carriers do not prove absence everywhere. Repository quarantine/evidence/host-carrier literal searches found no additional E-3145/E-3146 or Widget receipt carrier beyond the preserved report; recovery/archive/intake/log scopes were fully captured. The stale graph generation was treated as navigation only; untracked/changed/excluded paths were read directly. A clean coverage signal was not treated as exhaustive proof.

**SAIPEN: CONCURRENT_SOURCE_CHANGE.** The unrelated writer of current engine source changes is not identified. T-1698's owned candidate was preserved and rolled back with exact hashes; T-1697 remains intact. The earlier successful full-family snapshots do not certify this subsequently changed current source tree. T-1699 must resume only after that source ownership boundary and current required gates are resolved.

## 7. Can AUDAPACK resume normal SAIPEN work?

**No.** Normal admission, claim, transition and closure remain blocked until a supported, provenance-preserving recovery is established. Read-only diagnosis and preservation may continue. This report is the authorized forensic stop outcome; it is not a declaration that reconciliation succeeded.
