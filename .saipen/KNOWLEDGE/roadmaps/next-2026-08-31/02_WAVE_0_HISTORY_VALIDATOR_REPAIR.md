# 02 — WAVE 0: EMERGENCY HISTORY / VALIDATOR TRUTH REPAIR

## Goal

Restore the ability to trust the repository before continuing protocol compression.

No new feature work in this wave.

## W0.1 — Freeze current semantic edits

Do not continue cutting phase prose while historical truth is broken.

Preserve current phase changes in the working tree or a safe patch/checkpoint.

Do not ship them yet.

## W0.2 — Restore sealed LOG history

The current working tree deleted tracked:

`LOG-001..LOG-015`.

First determine why:

- accidental CLEAN/delete;
- bad archive restore;
- source archive migration;
- packaging omission;
- intended relocation.

The current repository contains no valid replacement authority.

If the deletion is accidental, restore exact tracked bytes from the current HEAD/tag history.

Do NOT:

- change E-4483 parent;
- fabricate E-4482;
- collapse history;
- create a fake DEC claiming recovery succeeded.

The canonical graph should become valid by restoring its real parent history.

## W0.3 — Verify history after restoration

Run:

- full LOG graph validator;
- event uniqueness/monotonic checks;
- parent resolution;
- sealed-segment digest/fingerprint checks where applicable.

The active LOG must reconnect to the sealed chain.

## W0.4 — Repair historical Improve linkage

For each failing CONFIRMED Improve finding:

1. identify its actual canonical Work if one exists in sealed/current LOG history;
2. restore truthful linkage;
3. if the original finding was never converted to Work, use the supported legacy reconciliation path;
4. never invent a ticket merely to satisfy the validator.

Once sealed LOG history is restored, some currently failing linkages may become discoverable automatically.

Re-run before editing Improve ledgers.

## W0.5 — Remove transport manifest from repository truth

`_AUDAPACK_MANIFEST.json` is package/export metadata.

Do not add it to ROOT_ALLOWED unless a separately ratified protocol change proves it belongs there.

Prefer:

- keep it outside repository root;
- exporter excludes it from source-tree validation;
- or `.gitignore` where appropriate.

## W0.6 — Re-run gates

Required:

- `tools/validate.py --gate core` → 0 FAIL;
- `tools/audit_checks.py` no longer fails because sealed history is missing;
- Audit Inbox focused tests remain green;
- registry tests green;
- continue/improve tests green;
- protocol budget green.

## W0.7 — Clean-checkout proof

Create a clean checkout of the repaired commit.

The same core gate must pass there.

Do not count a dirty-worktree PASS.

## Completion bar

1. sealed LOG segments restored or canonically relocated with full provenance;
2. E-4482 parent resolves;
3. historical Improve linkage passes;
4. root transport manifest no longer fails core gate;
5. clean checkout green;
6. no phase semantics changed in this wave.

Stop.
