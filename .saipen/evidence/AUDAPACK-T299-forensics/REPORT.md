# AUDAPACK T-299 lifecycle forensic report

Decision: **NO_GO for new AUDAPACK task admission or authoritative closure.**
Native integrity validation remains **CURRENT_FAIL**. No AUDAPACK lifecycle
repair was applied. The canonical recovery owner returned
`HISTORY_LEDGER_CORRUPT`, `FORENSICALLY_UNRECOVERABLE`,
`READ_ONLY_DIAGNOSIS_ONLY`, and `canonical_next_command: null`.

## Subject and preservation

- Actual project root: `V:/___VAC/__K/__CODE/_PY/_AUDAPACK`.
- Branch: `main`; HEAD: `6c6d841df24e5c5d91870def931af99f0af4c81f`.
- Portable lineage: `lineage-79944d6c0334416ebe1001e97de6c1cc`.
- Shared running SAIPEN version: `8.1.0`; persisted project `saipen_version: 7`
  is a different, historical field and does not identify the running engine.
- The existing dirty entry remained exactly
  `.saipen/improve/imp-vacterro-audapack-20260927-1/buffy-01/saipen_improve_SAIPEN.md`.
- The four canonical files are Git-tracked. The conflicting BOARD records,
  unnumbered Widget summary, and invalid STATE are already in HEAD; this is
  not merely an uncommitted working-tree discrepancy.

`snapshot-20261010T090700Z/ACQUISITION.json` records the original bytes,
SHA-256, length and source mtime for **8098 files / 76,363,816 bytes**.
The acquisition covered top-level `.saipen` files and recursive `logs`,
`recovery`, `quarantine`, `evidence`, `intake`, and `archive`, plus selected
root metadata. It is not a whole-project or whole-host image. Initial content
and selected file-set checks were stable; no links/reparse nodes were skipped.
Copied originals and the acquisition manifest were made read-only. A closing
comparison verified every acquired source and copy against its original hash:
**8098/8098 unchanged in each location**.

| Original file | SHA-256 |
| --- | --- |
| `.saipen/STATE.md` | `a766ca86d185ea24d4b1818f4295ef839826bcc913347047abcecf8dfcf5cc50` |
| `.saipen/BOARD.md` | `8bb2a5e68d474ee2ab22b834e6a94440d5389ea352d2969f5ad945cd04ca9952` |
| `.saipen/LOG.md` | `e414d4b54a3e99d9fa515945bf9d8be208581292889b3744edcb11466b0f7c7a` |
| `.saipen/MANIFEST.json` | `6bbb6ca8bed1502f04176d848f24ad12fdd58759e1946f0b2b27a5f023e0e050` |

Both engineering subjects remain accessible at their original locations and
in this case. Widget evidence is copied under the immutable acquisition at
`.saipen/evidence/T-299-widget-trust-boundary-p1a-p1b.md`. Additional source,
test, release and acceptance copies are in `provenance-capture/engineering/`.
The Widget userscript SHA-256 is
`5efa3a49fee7bdef83f63ecfa3324e2746eb12b874baad4e1bba03edd03a09fa`,
matching its retained engineering report. npm-cache source/tests and the
recorded RED/GREEN terminal outputs were preserved separately. Software
evidence does not establish admission or closure authority.

## Authoritative identities and heads

| Surface | Observed original | After investigation |
| --- | --- | --- |
| STATE | `DONE`, task `T-299`, `last_event: 3146`, `next_action: idle`, blocker none | Unchanged; invalid lifecycle state |
| BOARD | 280 physical task records, 279 distinct IDs, two completed T-299 records | Unchanged; both original rows preserved |
| Numbered event history | 3143 parsed events; numbered head E-3146 | Unchanged |
| Last event backed by an operation record | **E-3131**, closure of T-291 | Unchanged |
| Latest durable receipt by timestamp | `improve-rebind-b431fb0cacf0479daf67055c33ae053c`, COMMITTED, 2026-10-09T22:43:19Z | Unchanged; not a lifecycle closure or a replacement for E-3131 |
| Pending operations / conflicts | 0 / 0 | 0 / 0 |

The E-3131 lifecycle floor resolves to committed operation
`finish-29deadc9792e498ca581916d8a22c785`, agent `buffy`, created
2026-10-07T22:47:28Z, bound to the AUDAPACK lineage. The strict semantic receipt
snapshot decoded **4170 receipts**: 4166 COMMITTED, 3 RESOLVED, 1 ABORTED,
with no receipt decoding errors. No operation receipt in that snapshot names
T-298, T-299 or T-300. The snapshot's runtime path differs from the original;
all its receipts are settled and the same live-lineage authority assessment
was repeated against the original project in `final-checks.json`.

The complete active/sealed history lacks **E-3133, E-3136 and E-3145** even
though E-3134, E-3137 and E-3146 name them as parents. No numbered E-3147
was found. A bounded scan of acquired text/recovery copies also found none
of these four numbered event lines. This does not prove that no unavailable
external backup exists.

E-3132 through E-3146 contain twelve parsed events with no operation backing
above the E-3131 floor. The authority owner identifies unbacked terminal rows
T-278 and T-292 through T-299. Its parsed T-299 projection is the first,
Widget row; the original duplicate error remains visible and prevents treating
that projection as attribution to either engineering task.

The operator's stated identity decision is preserved: **npm-cache keeps
T-299**. This instruction does not retroactively validate the npm-cache
admission or closure. **Both T-299 closure claims remain unverified.**
Widget receives no new task ID in this investigation. T-300 was not allocated.

## Root cause and writer attribution

| Finding | Classification | Evidence and limits |
| --- | --- | --- |
| npm-cache lifecycle was written outside SAIOPS | **PROVEN** | FreeBuff assistant message 198 contains direct BOARD/STATE replacements and a successful shell append of E-3146 |
| Responsible recorded npm-cache session | **PROVEN** | FreeBuff thread `f267f617-a0f8-47f5-b617-b9393f0e61d2`, title `AUDAPACK Widget Clock Hardening`, harness `codebuff`, stored model `m-ffcbc2bcf3`, project path AUDAPACK |
| Physical E-3146 append succeeded | **PROVEN** | Tool `Hv6xaJCnQyc`, `run_terminal_command`, `status: success`, `exitCode: 0`, output `ok`; exact appended event matches retained LOG |
| BOARD/STATE direct replacement invocations occurred | **PROVEN** | Tool IDs `Hv2FiCaDaTc`, `Hv2HSmGZS5E`, `Hv6ke1z_xtc`, `Hv6l3jOa0ac` with exact replacement inputs; their stored parts omit individual result statuses, so successful execution is not separately proved by those parts alone |
| E-3145 represented a committed admission | **NOT PROVEN** | A replacement input set STATE to 3145; no E-3145 event or admission operation was found |
| Widget row and unnumbered completion bypass canonical lifecycle proof | **PROVEN** | Original bytes, strict parse/ledger errors, absence of related receipts above the floor |
| Individual process/model that inserted Widget's duplicate and malformed heading | **UNKNOWN** | Both changes are in HEAD under Git author/committer `VAC34`; commit metadata and self-declared `owner: buffy` do not authenticate the editing process |
| Sequential out-of-band reuse of T-299 | **LIKELY** | npm-cache session records T-299 before the later retained Widget change; both rows survive in one commit, without a new allocation receipt |
| Concurrent writers, allocator failure, restore/merge origin, or misapplied documented recovery caused the duplicate | **UNKNOWN / not demonstrated** | No matching canonical recovery receipt; no proved overlapping writers; allocation and writer-lock controls passed sacrificial tests |

The captured FreeBuff database is a consistent WAL-aware SQLite backup from
a read-only connection, scoped to AUDAPACK's project-ID directory. Its hash is
`e9c588bf1ea22c9310ec1c94ef6474061da66b657ed89483317dd94996e7bd8e`.
`freebuff-acquisition.json` records its source and capture time.
`writer-and-engineering.json` addresses the specific message/tool parts.
Message 198's stored timestamp is 2026-10-09T04:50:10.700Z; the appended LOG
line claims 09.10.26 03:15. Neither timestamp was rewritten or promoted into
historical authorization. These are local forensic records, not an
authenticated operator-ingress receipt or proof of a human author's identity.

Root cause established here: lifecycle truth was replaced with direct Markdown
writes, creating a typed completion and marker without the operations that
would allocate, verify, close and journal them. The Widget row also claims
that task ID without supporting lifecycle proof. Passing engineering tests
cannot repair the missing authority.

## Authorized operations and reconciliation decision

Performed against live AUDAPACK:

1. Read-only acquisition and Git root/branch/HEAD/status/history observations.
2. Documented native validator with `--gate core --no-receipt`, twice.
3. `bin/saipen.cmd recover --project-root AUDAPACK --dry-run --json`, twice.
4. Read-only history, receipt and lifecycle-authority owner evaluations.

**No lifecycle mutation, task reassignment, heading edit, counter reset,
claim, transition, admission, receipt rewrite, closure or historical event
insertion was performed.** `--no-receipt` kept validation from adding a new
conformance artifact to the original project. All investigation outputs went
to this separate case directory or disposable test projects. No consumer
project was granted an exception or changed.

The existing `recover --resolve-duplicate-id` owner can bind the two exact
record digests and allocate a new ID atomically; no second allocator is
needed. The current digests are:

- Keep npm-cache T-299: `4a92ef79bd7c77c1076a44ecc23acb331cf77427273711440c07b848ec284c95`.
- Widget record: `1b028a689439ac0579d23743f129e3884e8bfb358ba91c725b14883a7b0d9392`.

That operation changes the losing row's identity token while preserving its
other text. By itself it would not establish Widget admission, revoke an
unverified closure, repair the missing event parents or fix the headings.
It was therefore **not executed**. The existing recovery owner refuses
planning over this ledger and explicitly supplies no safe automatic repair.

The pure `foreign_tail_cut` predicate was evaluated without invoking a
mutating command. It refused: the unnumbered Widget summary at LOG line 2
is damage before the checkpointed tail, so cutting the later unbacked head
would leave an invalid ledger. Missing event IDs were not invented, LOG
parents were not silently changed, and the summary was not numbered as a
historical completion. The malformed heading remains visible rather than
being disguised by a raw Markdown repair.

## Enforcement results

The sacrificial baseline was a separate Git project with genuine canonical
operations establishing its ledger and claim; native validation passed
before faults were introduced. Raw fault injection occurred only in these
disposable fixtures. `enforcement-results.json` contains exact invocations,
exit codes, outputs and output hashes; fixture directories were retained.

| Sacrificial fault/control | Result |
| --- | --- |
| Duplicate IDs with different task descriptions | Native FAIL: duplicate T-001 |
| New closed T-999 without canonical admission/closure | Native FAIL: no allocation event and lifecycle authority violation |
| Unnumbered LOG completion | Native FAIL: Event Graph skeleton |
| STATE.last_event ahead of durable history | Native FAIL: lifecycle authority, STATE above journal floor |
| Concatenated/missing lifecycle headings | Native FAIL: missing required TODO/DOING headings |
| Conflicting restored assigned ID | Native FAIL: restored duplicate T-001; loss of an allocated T-2 row did not allow reuse, next allocation was T-3 |
| Concurrent writer | Canonical mutation refused `WRITER_BUSY`; core hashes unchanged |
| Foreign live claim takeover control | Refused `TICKET_NOT_WORKABLE`: active claim belongs to `buffy`; core unchanged |
| Read-only native validation while mutex held | PASS, as expected: validation observes, canonical mutation admission owns exclusivity |

All seven requested enforcement probes behaved correctly in the bounded
scenarios tested. A read-only validator passing under a writer mutex is not
evidence that a second writer was admitted. These results do not prove every
possible restore or concurrency scenario safe.

The existing regression owners were then run:

```text
python -m unittest test_t1671_lifecycle_authority test_t1673_board_only_terminal test_t1679_typed_head_quarantine -v
cwd: <SAIPEN>/tools
exit: 0
Ran 31 tests in 71.127s
OK
```

`focused-regression.json` records the interpreter, command and output hash.
The seven custom probes are separate from those 31 unittest cases; they are
not represented as a larger full-core test count. The full SAIPEN or AUDAPACK
software suites were not run. A previous unrelated 6027/0/0 result is not
evidence of current AUDAPACK protocol integrity.

The first fixture setup attempt failed native validation because its temporary
Git repository had no HEAD and its lineage file was untracked. The harness
was corrected by committing only the sacrificial fixture files, then the
clean baseline and all fault cases ran. That setup failure was not counted as
a protocol defect or as red-before-green production evidence. An initial
read-only analysis helper also used a nonexistent validation function; it was
corrected to the existing `snapshot_contract_errors` owner. Neither issue
changed AUDAPACK or production source.

## Native validation and remaining blockers

Both live native runs exited **1**, with **19 problems / 79 warnings**.
Both recovery previews exited **1** with the same integrity refusal.
Full output is in `native-before.txt`, `native-after.txt`,
`recover-preview-before.txt` and `recover-preview-after.txt`.
The read-only `response digest --project-root AUDAPACK --reason safety --json`
also exited 1, `RESPONSE_FACT_INVALID: canonical status unavailable`. A healthy
canonical status digest was therefore not fabricated for this invalid project.

Blocking findings include duplicate T-299; missing TODO/DOING headings;
unnumbered Widget completion; missing parent events; invalid DONE/task,
transition and next_action fields; unsupported BOARD evidence fields and a
historical closure mode; and a stale improve report fingerprint. The original
MANIFEST was preserved. Agreement among STATE, BOARD, LOG, MANIFEST and
recovery receipts has **not** been achieved. Warnings were not cleared on the
strength of software tests. Because BOARD parsing fails, an empty parsed
DOING set is not a trustworthy clean-ownership certificate; no claim was
taken and no lock was forcibly released.

No global SAIPEN enforcement defect was reproduced by these tests, so no
new shared-engine correction or enforcement ticket was created on suspicion.
Production source changes from the earlier, separate T-1704 continuation
mission predate this forensic work and are documented in
`../T-1704-draft/applied.json`; they are not AUDAPACK repairs. This investigation
adds only case evidence/helpers and temporary fixtures.

Graph evidence was Tier 2, projects `saipen` (generation
2026-09-01T13:16:39Z) and `audapack` (2026-09-14T08:58:13Z). SAIPEN's tools
and AUDAPACK recovery/docs were excluded from their graphs, and canonical
Markdown metadata had changed. Coverage checks were followed by direct
source/byte reads of the bounded evidence; no graph-completeness claim is
made. The source fingerprint in `engine-subject.json` is an end-of-run
content inventory, not an authenticated historical operator grant.

## Admission gate and required unblock

**NO_GO. Exact next executable AUDAPACK lifecycle action: NONE.** The current
canonical recovery response exposes no admissible next command and no
operator decision that this run can safely convert into a repair.

The operator already decided that npm-cache keeps T-299. Repeating that
permission would not restore the missing journal truth. A safe next repair
requires either genuine recoverable historical evidence/snapshots, or a
separately documented, explicitly authorized forward-only quarantine and
reconciliation operation that preserves the disputed bytes and records
unverified work without fabricating old events. No such new operation or
approval was invented here. The operator boundary comes from the mission's
STOP instruction and the actual integrity refusal, not a numerical work cap.

After an admissible repair, all identities, admission/closure lineage,
headings, event parents, state marker, manifest and receipt bindings must
agree and repeated native integrity validation must pass. Only then may a
fresh canonical task admission allocate an ID from BOARD plus complete LOG
history. Widget would need a valid present-time reconciliation/admission and
independent verification before any authoritative closure; its existing
engineering evidence remains available throughout.
