# SRC-205 A04: current read-only AUDAPACK evidence matrix

This satisfies the bounded A04 evidence investigation, not recovery or consumer
admission. `A04-current.json` binds the exact current reads and command outputs.
The existing broader acquisition and attribution are retained unchanged in
`../AUDAPACK-T299-forensics/REPORT.md` and its sealed case. This recheck does not
claim to have searched every unavailable external backup or all 8171 case files.

| A04 requirement | Current evidence | Classification and limit |
| --- | --- | --- |
| Canonical core fingerprints | SHA-256 of STATE, BOARD, LOG and MANIFEST before/after all match the four original forensic values | Current originals unchanged; no live core mutation |
| Missing parents E-3133/E-3136/E-3145 | Complete active/sealed history owner confirms absent parents of E-3134/E-3137/E-3146 | Missing from current complete canonical history; unavailable external backups remain unknown |
| Trusted operation floor E-3131 | Current `lifecycle_authority.assess` computes floor 3131 | The journal-backed floor remains distinct from numbered head E-3146 |
| Typed tail | Twelve events above the floor remain UNAUTHORIZED | Their text is preserved; it is not canonical operation proof |
| Nine unsupported terminal claims | Current owner lists T-278 and T-292 through T-299 | The duplicate T-299 projection cannot independently attribute both engineering rows |
| Malformed BOARD | Current shared parser rejects duplicate T-299, missing DOING/TODO headings and unsupported evidence fields | Empty parsed ownership is not a clean-seat certificate |
| Invalid STATE marker | DONE retains task T-299, last_event 3146 above floor 3131, and next_action idle | The shape and authority both remain invalid |
| Status to recovery boundary | Actual status: UNAUTHORIZED_LIFECYCLE_WRITE, action `saipen recover`; actual dry-run recovery: HISTORY_LEDGER_CORRUPT, FORENSICALLY_UNRECOVERABLE, no next command | Recovery is a diagnostic, not an available repair. No mutating retries were attempted |
| `next` comparison | Actual next: VALIDATION_FAILED, checkpoint-invalid, action `saipen recover` | The three surfaces still expose different primary refusals; A05 remains separate and uncompleted |
| Current native integrity | Actual `validate.py --gate core --no-receipt`: exit 1, 20 problems / 79 warnings | CURRENT_FAIL; software tests do not repair this ledger |
| Writer attribution and uncertainty | Existing sealed FreeBuff evidence proves out-of-band npm-cache lifecycle invocations and successful E-3146 append; Widget's individual writer remains unknown | Git author and self-declared owner do not authenticate a process; no new historical actor was invented |

Current hashes:

- STATE.md: `a766ca86d185ea24d4b1818f4295ef839826bcc913347047abcecf8dfcf5cc50`
- BOARD.md: `8bb2a5e68d474ee2ab22b834e6a94440d5389ea352d2969f5ad945cd04ca9952`
- LOG.md: `e414d4b54a3e99d9fa515945bf9d8be208581292889b3744edcb11466b0f7c7a`
- MANIFEST.json: `6bbb6ca8bed1502f04176d848f24ad12fdd58759e1946f0b2b27a5f023e0e050`

The extra current native finding, relative to the retained 19-problem result,
is audit-route-not-followed for pending `audit/AUDAPACK_20261010_1411.md` against
the unchanged `next_action: idle`. No historical failure output was rewritten.
The current source improve fingerprint is also different, as expected after
engine changes; its existing stale-report finding remains a failure.

All four commands are read-only or explicit recovery preview; native validation
uses `--no-receipt`. Raw outputs and their SHA-256 values are in
`A04-status.txt`, `A04-recover.txt`, `A04-next.txt`, `A04-native.txt` and the
immutable current JSON receipt. The before/after core comparison passes.
No consumer repair, claim, admission, source edit, lifecycle closure, event
creation or fabricated parent was performed. AUDAPACK remains NO_GO.

The parent T-1702 and SRC-205 retain their other uncompleted slices and operator
gates. A04's truthful evidence delivery cannot settle A05/A06 or OS isolation.

The explicitly required focused recovery-authority families were also executed:
`python -B -m unittest tools.test_reconcile_history_ledger_blocked tools.test_t1671_lifecycle_authority tools.test_ledger_gap -q`.
Actual result: 32 ran, PASS, exit 0, 53.919 seconds; the capture reports source
unchanged. Immutable command/output evidence is
`../T-1706-hot-switch/cc-all-a04-focused.json` and its `.txt` file.
These fixture checks do not change the original consumer's CURRENT_FAIL or
establish a supported live recovery operation.
