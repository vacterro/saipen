# TEST-17 -- adversarial scenarios at dc39709c / tree 1a368781

- source_head: dc39709c0c17a3272126c01a626ffcaa4176140b
- source_tree_fingerprint: git-delta-v1:1a368781b8bbe259b5218e35666c2732b2531304247854b750c561f1f888ada9
- role_revision: sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08
- epoch context: converge_intent-f74cb6f3247c405fbf754e4a71a9eee5 (SC-3, T-2070/T-2071 payload in the worktree)
- mode: read-only toward the main tree; probes are read-only or refused before writing

## S1 -- damaged state: the audit-route dead end (family 3/7)

TEST-16 reproduced the dead end at tree c9c3e86c: the validator demanded
`saipen audit ingest` while the executor refused it. Re-run at the current tree:

- routing: `projection('.', tickets=parse_board(BOARD))` = action `saipen audit ingest`,
  work `T-2016`; `audit_route_owns` -> **False**; `route_violation(projection,
  'saipen crew')` -> **None** (`_test17_route_restore_probe.txt`).
- executor: `saipen audit ingest --dry-run --json` -> `SOURCE_UNRESOLVED`, "linked Work
  T-2016 is not DONE", exit 1, no writes (`_test17_s1_ingest_probe.json`).
- gates: the repo-generation validator carries **no** audit-route FAIL
  (`_hunt022_repo_validate.txt` is at the same tree); the installed validator still
  carries it because its engine predates the payload.

**Verdict: NOT_REPRODUCED** at the current routing level. The executor's refusal is
correct and still measured; what is gone is the contradiction -- the router no longer
orders an action the executor refuses. Two-sided by construction: the router falls
through, the executor keeps its gate.

## S2 -- environment: the two validator homes (family 7/7)

Same project, same validator rule text, different home manifest:

- installed home (`saipen validate --json`): 3 problems / 18 warnings --
  SRC-418/T-2072, audit route, FG-0046/T-1936.
- repo generation (`python -B tools/validate.py`): 29 problems / 38 warnings --
  SRC-418/T-2072, 27 runtime-manifest untracked paths, EX-000053 provenance.

The class difference is exact: the installed generation sees the two payload-repaired
classes (pre-fix engine), the repo generation sees the manifest and EX classes
(post-fix engine, repo manifest). Both counts are measured, not inherited.

**Verdict: REPRODUCED** (asymmetry survives the payload; it is a publication/home
identity condition, already owned by T-2058/T-1449/T-2052 -- no new ticket).

## S3 -- order and repetition: crew planning is idempotent (family 3)

Two consecutive `saipen crew --dry-run --json` at the same snapshot:

- both exit 0, both `CREW_PLAN`, `first_unsatisfied` SC-3, action `RUN_ROLE saitest`,
  `source` dc39709c/1a368781, snapshot `state b34059ae2a84a881`, `board 43311369612a2f7d`,
  `stable: true`, `log_tail 21291` (`_test17_crew_a.json`, `_test17_crew_b.json`).
- `.saipen/STATE.md` and `.saipen/LOG.md` hashes are byte-identical before and after
  (`_test17_pre.sha`, `_test17_post.sha`, diff empty).

**Verdict: REPRODUCED** (positive): replay neither advances the stage nor writes state.
The SC-2 -> SC-3 move was made by the committed receipt, not by plan reads.

## S4 -- input abuse: a foreign/unknown package is refused (family 1)

`saipen crew record-run saitest --package TEST-99 --json` -> `STALE_PACKAGE`, exit 1,
"TEST-99 is not a current saitest package"; STATE/LOG hashes unchanged
(`_test17_s4_probe.json`). A package ID that does not carry the live source triple and
the current role revision is refused by the writer, not coerced.

**Verdict: REPRODUCED** (refusal holds).

## S5 -- boundary: restoring a row that is already present (family 2)

Direct helper boundary: `board_scrub.restored_board_text(text, [row])` on a text that
already contains that exact row **duplicates it** (1 -> 2 occurrences) and the
duplicated record no longer parses (`section None`) -- `_test17_route_restore_probe.txt`.

Reachability: the canonical verb never reaches that state. `restore_board_rows`
computes `gated_missing = gated - set(board["tickets"])` and refuses
`NOTHING_TO_RESTORE` when nothing is missing (operations.py:27064-27079), then hands the
helper only pruned rows. The duplication is therefore a latent helper property, not a
reachable verb failure; recorded as a limit, not a ticket.

**Verdict: NOT_REPRODUCED** as a reachable failure.

## Limits

- S1 measures the routing projection and the executor refusal separately; it does not
  run a full ingest to completion (no layer is deletable: T-2016 is open).
- S2 is a count/class comparison; no rule-by-rule identity audit of the two engines.
- S3/S4 use the CLI's own JSON; no journal internals inspected beyond hashes.
- No main-project file was written by this role.
