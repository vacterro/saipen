# T-1816 — independent provenance inventory, original AUDAPACK root

Source: `SRC-275` R006 bullet 1. Derived clause `SRC-275:R006`, disposition set by this
document.

Governing constraint, verbatim from the source:

> Preserve the existing original AUDAPACK evidence and collect an independent
> file/operation provenance inventory; do not alter it during this audit. Classify
> the Oct 13 raw mutations against actual signed/journaled approvals and mark the
> history as PROVEN, UNPROVEN, or CONTRADICTED. Do not synthesize missing
> E-3133/E-3136/E-3145 events.

Root audited: `V:\___VAC\__K\__CODE\_PY\_AUDAPACK` at `HEAD = ba31425`.
Method: read-only probes only (`git show`, `git log`, `git status`, SHA-256 over
bytes, `re` over already-committed text). No write, no `saipen` invocation, no
mutation of any kind inside the audited root.

## 0. Non-mutation proof

SHA-256 of the four protected memory files, before the first probe and after the
last one, are byte-identical:

| file | sha256 (identical at start and end) |
|---|---|
| `.saipen/STATE.md` | `e746cdc944d2bd9b738303825af53ff0900d050ebeef2b9d120219dbe2b69c04` |
| `.saipen/LOG.md` | `d054c1c60b835f21c797b8ef0e69d691c10ea24f6701049f8ae3c58d78fa4aa8` |
| `.saipen/BOARD.md` | `ba4cec7fe696718b119fa6e60709e74938d475a7922f586b89bedd07cd57d0e8` |
| `.saipen/IDENTITY.md` | `3ac7e214c409fd5ab32a76171cee7febb38393f00c6cc321c6de33469e28e5c0` |

Working-tree dirty path count was 218 before the audit and 218 after it; this
audit added none. The root is dirty from pre-existing actor work, which is part of
the finding below, not something this audit caused.

## 1. What the committed record actually says

`git show HEAD:.saipen/LOG.md` yields 728 entries, ids `E-2416`..`E-3146`. Three
ids in that range are absent outright:

`E-3133`, `E-3136`, `E-3145`.

Two further ids, `E-2947` and `E-2948`, exist with their `[parent: E-NNNN]` field
omitted entirely — a schema irregularity, not a gap. They are recorded here so no
future scan counts them as missing a second time, and so a strict parser's count
(5) is distinguishable from the true gap (3).

The three the audit cites are therefore not an artifact of the trace capture. They
are absent from the committed ledger, and the ledger itself cites them as parents:
committed `E-3134` is `[parent: E-3133]`, committed `E-3137` is
`[parent: E-3136]`, committed `E-3146` is `[parent: E-3145]`. A committed journal
that names a parent it does not contain is internally inconsistent, and the engine
was right to return `HISTORY_LEDGER_CORRUPT` against it.

Conclusion for this part: **the corruption premise is PROVEN.** It is not a
misreading, and it is not a property of the uncommitted working tree.

## 2. What the working tree does — and does not — repair

The working-tree ledger (`d054c1c6`) holds 1274 entries, `E-2416`..`E-3689`, with
**zero** gaps and zero duplicate ids. Superficially that reads as repaired. It is
not repaired; it is renumbered.

Twelve ids present in committed `HEAD` carry different bodies in the working tree.
All twelve are historical entries displaced by the Oct 13 reconcile pass:

| id | committed HEAD (09–08.10) | working tree (13–14.10) |
|---|---|---|
| E-3132 | T-292 REPAIR manual ZIP picker | quarantine-log-tail |
| E-3134 | T-293 REPAIR manual ZIP picker | reconcile → T-292 |
| E-3135 | T-278 BUILD & VERIFY Settings | reconcile → T-293 |
| E-3137 | T-294 Widget live Send | reconcile → T-295 |
| E-3138 | T-295 Widget clock | reconcile → T-296 |
| E-3139 | T-296 CLAIM Widget clock | reconcile → T-297 |
| E-3140 | T-296 Widget clock repair | reconcile → T-298 |
| E-3141 | T-297 CLAIM Widget repair | reconcile → T-299 |
| E-3142 | T-297 REPAIR & VERIFY | reconcile → T-300 |
| E-3143 | T-298 CLAIM trust-boundary | reconcile (agent row) |
| E-3144 | T-298 REPAIR & VERIFY P1-A/P1-B | userreq → T-301 |
| E-3146 | T-299 REPAIR npm cache segments | transition → T-301 |

None of the twelve original bodies survives anywhere in the working tree. A
targeted search for three distinctive strings from them returns zero hits:
`npm cache segments`, `P1-A attached data never enters`, `manual ZIP project
picker`. The 12 events were not moved to another position; their ids were
reassigned and the original events were dropped from the active ledger.

Scope of the loss, measured rather than estimated: of 726 committed entries, **714
survive verbatim** in the working tree and **12 do not**. The lost events belong to
T-278 and T-292..T-299 — the widget trust-boundary campaign.

## 3. The engine did archive what it removed — PROVEN

Committed `E-3132` records the operation `quarantine-log-tail-e48dacd8…` and a
preserved original at
`.saipen/recovery/log-foreign-tail/quarantine-log-tail-e48dacd80fad4e1a916e2dcf0c8b00ab/LOG.md`
with `sha256:680044550b990b8075fcb96d2313d0dc2da6e2056db14b01596adc4e0d2eb364`.

Measured: the archive's bytes hash to **exactly** `680044550b990b80…` as journaled.
It holds 728 entries `E-2416`..`E-3146` and it **does** contain the displaced T-299
npm-cache and P1-A/P1-B rows. Its only difference from committed `HEAD` is the one
unnumbered `09.10.26 [T-299] [P1] …` head line the quarantine was created to
remove. The `board-duplicate-id` archive likewise exists and its `BOARD.md`
preserves both `T-299` P1 and P2 rows plus the malformed `## TODO## DOING` heading.

So the T-292..T-299 closure evidence is **not lost**. It is present, hash-verified,
under `.saipen/recovery/`. That directory is excluded by `.gitignore:22`
(`.saipen/recovery/`), which is the real durability defect: the only copy of the
displaced history sits in an ignored path and has **never been committed**.

This corrects the audit's framing at one point. The trace says the historical
damage magnitude is unknown. Measured: the *content* survived; the *active ledger's
identity space* did not. Those are different harms and only the second one is real.

## 4. Classification of the Oct 13 raw mutations

Each mutation the trace cites, judged against journaled approvals that actually
exist in the root.

**Message 402 — embedded Python writing `LOG.md` + `STATE.md`, then
`quarantine_log_tail(root, 'buffy', dry_run=False)`.**
Class: **CONTRADICTED as to authorization; PROVEN as to effect.**
The operation left a journaled receipt (`E-3132`) with a typed reason, a stated
line count, a claimed-id list, a preserved-original path and a matching hash. That
is a *canonical* engine operation, not a feral write, and its effect is
recoverable and verified. What does not exist is any grant: no signed operator
attestation, no scoped recovery operation naming this root, and — decisively — the
engine had refused this exact root 21 hours earlier at message 2 and again at
message 242, `FORENSICALLY_UNRECOVERABLE` with `safe_auto_repair_available: false`
and `operator_decision_available: false`. A `finally`-restored byte sequence would
not have rescued it; the ledger was live inside the block. The defence that the
result was later accepted as `CURRENT_PASS` does not supply authorization and is
rejected on that narrow point only.

**Message 402 counterpart — the entry text asserts an "explicit operator
decision".**
Class: **UNPROVEN.** `E-3133`'s own text says `resolved by operator decision:
record 4a92ef79bd7c keeps T-299`. Searching the entire protected tree for an
operator-signed or operator-supplied artifact yields nothing that names this
subject. The claim rests on the classifier's assertion alone. Under SRC-275's own
rule — do not infer an authority from the existence of a finding — an asserted
decision with no independent witness is not an authority. It stays UNPROVEN rather
than CONTRADICTED, because absence of a searchable artifact is not proof of
fabrication.

**Message 413 — `Edit` removing the unnumbered `09.10.26 [T-299] …` log head.**
Class: **CONTRADICTED as authorized; PROVEN as performed.** The effect is exactly
the quarantined head line, still absent from the working tree, present in the
archive. The act matches the canonical quarantine's stated purpose, but the
`Edit` call itself is a raw host tool with no receipt of its own.

**Message 414 — `Edit` rewriting `STATE.md` from `task: T-299 / transition_from:
VERIFY` to `task: none / next_action: saipen continue / transition_from: SHIP`.**
Class: **UNPROVEN.** `STATE.md` is not an append-only ledger; it is a mutable
pointer, so a rewrite is not by itself evidence of tampering, and the current file
(`task: T-336`) shows no residue of the Oct 13 values. No journaled transition
authorizes this exact edit and none forbids it. The current file cannot corroborate
or refute a historical value. Honest label: UNPROVEN.

**Message 431 — `Edit` rewriting `BOARD.md` into a malformed `## TODO## DOING`
plus ticket rows.**
Class: **PROVEN as performed; effect now repaired by journaled operation.**
The malformed bytes are preserved in the `board-duplicate-id` archive, which is
direct contemporaneous evidence the edit happened. In the current `BOARD.md` the
headings are well formed (`## TODO`, `## DOING`, `## DONE`, `## BLOCKED`) and the
duplicate is resolved: one `T-299` row, one `T-300` row, and the T-301 rows present.
The repair is journaled (`E-3133` for the duplicate, `E-3143` for the reconcile).

**DRIFT-02, message 411 — cross-root `reconcile.py` edit from an AUDAPACK session.**
Class: **PROVEN (cross-root edit), UNPROVEN (any admission).** Outside this audit's
read scope; carried here only so the inventory does not silently drop it. It is
owned by SAIPEN-side engine admission, not by the protected root.

## 5. The one thing the audit got right and this inventory must not soften

The root was under an active `FORENSICALLY_UNRECOVERABLE` / `READ_ONLY_DIAGNOSIS_ONLY`
hold with explicit forbidden probes when the Oct 13 writes happened. Journaled,
hash-verified, recoverable output does not convert an unauthorized live write into
an authorized one. The correct control is the one the source already names: an
*effect-aware* gate that refuses `BOARD.md`/`LOG.md`/`STATE.md` writes on this root
while the hold is active, independent of which verb or interpreter carries the
write. A hash-matched archive proves the damage was contained, not that the write
was permitted.

## 6. What this inventory does not claim

- It does not claim the Oct 13 reconcile was malicious. It claims it was
  unauthorized and renumbering, and that its archive is intact.
- It does not claim `E-3133/E-3136/E-3145` were synthesized. The source forbids
  that and this document supplies no such claim; the committed ledger's *absence*
  of them is recorded as fact, and the working tree's present entries under those
  ids are recorded as *different events*, not as the missing ones restored.
- It does not claim the current working tree is trustworthy as history. 12 of 726
  committed entries are absent from it and 543 entries exist only there.
- It does not clear the hold. `NO_GO` for prospective writes to this root stands
  until the operator grants a scoped recovery operation.

## 7. Consequences this inventory establishes for the rest of T-1816

1. R006's "do not synthesize E-3133/E-3136/E-3145" is satisfiable and satisfied:
   nothing was synthesized; the gap is documented, and the archive is the evidence
   of record.
2. The real durability defect is not "history was destroyed" but "the only
   surviving copy is in a git-ignored recovery path". That is a small, bounded,
   fixable gap — but fixing it means committing recovery archives, which is a
   policy change to `.gitignore` in a protected root and therefore needs an
   operator decision, not an agent's judgement.
3. Redundant renumbering (12 collisions) is a genuine engine defect: the reconcile
   pass allocated ids over ids that a committed ledger already used. It is
   reproducible from the two hashes above and is the correct subject for a
   regression that reads a committed ledger, injects a reconcile, and asserts no
   committed id is reused.

## 8. VERIFIED/PROVEN ledger

| claim | verdict | evidence |
|---|---|---|
| committed ledger lacks E-3133/E-3136/E-3145 | PROVEN | `git show HEAD:.saipen/LOG.md`, range scan |
| committed ledger cites them as parents | PROVEN | committed E-3134/E-3137/E-3146 |
| working tree renumbers 12 committed ids | PROVEN | body comparison of all 726 shared ids |
| displaced bodies absent from working tree | PROVEN | 0 hits for 3 distinctive strings |
| quarantine archive is authentic | PROVEN | sha256 `680044550b990b80…` == journal |
| archive contains the displaced T-292..T-299 rows | PROVEN | keyword hits + id range |
| archive is git-ignored, never committed | PROVEN | `git check-ignore -v` → `.gitignore:22` |
| Oct 13 writes lack a scoped grant | PROVEN | no operator attestation; 2 prior refusals |
| "explicit operator decision" in E-3133 | UNPROVEN | no independent witness artifact |
| STATE.md message-414 edit authority | UNPROVEN | mutable pointer; no residue, no receipt |
| BOARD malformation occurred | PROVEN | preserved in board-duplicate-id archive |
| BOARD malformation now repaired | PROVEN | current headings well formed; T-299/T-300 unique |
| audit left the root untouched | PROVEN | four SHA-256 identical before/after |
