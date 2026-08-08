# Phase: PREPARE

Entered by explicit user command: `saipen prepare [producer]`.

This phase is primarily used by specialized roles and subSaipens (e.g., `saitranslate`, `saiwiki`, `saihunt`) to finalize their work and package it for the next agent (usually the main project agent) to consume. A named producer scopes one complete deliverable; it is never permission to substitute a quick scan.

1. **Forced-fresh preparation**: A named producer preparation is regeneration,
   not reuse. Run `saipen sub sync`, load the current project-local charter,
   derive its `role_revision`, inspect the current project, and invalidate any
   prior package whose `source_head + source_tree_fingerprint + role_revision`
   does not match. Rebuild the producer output and rerun its verification. A
   no-op is legal only when the producer has a deterministic cache contract
   that proves byte/content-equivalent regeneration against all three current
   freshness inputs; the cache proof and the freshly rerun verification belong
   in `verified`. Merely finding an earlier `status: ready` package is never a
   cache proof.
2. **Core Result Formatting**: Assemble your final artifacts (code, translations, documentation, or hunt reports). Ensure they are complete and structurally sound.
3. **Comprehensive Instructions**: Write a clear, step-by-step guide for the *next agent* explaining exactly how to inject or use this core result in the main software. Assume the next agent has zero context about your internal process.
4. **Delivery**:
   - Every collectable handoff MUST include these fields: `status`, `producer`, `source_head`, `source_tree_fingerprint`, `role_revision`, `coverage`, `payload`, `verified`, and `instructions`. Compute the final source identity only after the producer's last source-affecting read/mutation and immediately before writing the package. `status: ready` is legal only when coverage is complete, all three freshness values are current, producer-side checks passed, and the payload plus injection instructions are executable without guessing. Any freshness computation/read/stat/classification failure writes `status: blocked`; unknown input is never skipped. Otherwise write `status: draft` or `status: blocked` and state the gap.
   - If you are running as a subSaipen (CORE.md §1.9), write the combined result and instructions into your `kitchen/OUTBOX.md`, and mark your current ticket as `[x]` in `## DONE` only when the handoff is ready.
   - `saipen prepare saitranslate` (`ee`) FORCE-FRESH executes the complete TRANSLATE contract over every real documentation and in-app UI surface, then writes `.saipen/saitranslate/kitchen/OUTBOX.md`. Its `coverage` enumerates every discovered source surface and every required locale; its `payload` enumerates the exact files to integrate. It MUST NOT touch main-project files.
   - `saipen prepare saiwiki` (`qq`) FORCE-FRESH spawns or adopts `saiwiki` if needed, completes the current wiki maintenance scope, then writes `.saipen/extensions/subs/saiwiki/kitchen/OUTBOX.md`. Its `coverage` enumerates every maintained page and relevant source invariant; its `payload` enumerates the exact pages to integrate. It MUST NOT touch the main project or wiki remote.
   - An unqualified main-project preparation may place a non-collectable package in `.saipen/kitchen/`; it MUST NOT impersonate a named producer's ready handoff.
5. **Isolation**: PREPARE packages only. It MUST NOT integrate the payload into the target, modify a target remote, commit, tag, or push. Those belong to `saipen collect <producer>` followed by the normal Core gates and an explicit SHIP chain. Core may refuse a stale package but may never refresh its freshness fields; only this producer preparation writes replacement evidence.
6. **Completion**: LOG one Event Graph line per CORE.md §1.2 -- `- DATE
   [E-###] [parent: E-###] RUN: prepare <producer> -> done` -- then
   `STATE.phase -> DONE`. Preparation failed (freshness check found the work
   stale beyond repair, or delivery target unwritable)? LOG
   `RUN: prepare <producer> -> FAILED <reason>` (this exact text after the
   taxonomy) instead, then `STATE.phase -> BLOCKED` with the facts.

   **`<producer>` is required in both, and the word `unqualified` is the
   producer name when no producer was requested.** The record said
   `RUN: prepare -> done` for `saitranslate`, for `saiwiki`, and for an
   unqualified main-project package alike, so a cold agent or `saipen status`
   reading the LOG could not tell which handoff became ready, and two prepares
   were indistinguishable rather than dedupable. Live agents had already
   started writing the producer in by hand, against this document's own fixed
   format -- practice correcting a shape nobody had fixed. This is § 1.2's
   `RUN: validate.py -> PASS|FAIL` argument one phase over: a record another
   rule is required to READ needs a form the reader can find, or the reading
   is invention.

   **The source revision is deliberately NOT repeated here.** The handoff's
   own `source_head:` field (step 4) already carries it, per producer, and a
   second copy in an append-only file is a copy that can go stale against the
   one that gets refreshed. The LOG line answers "which prepare ran, and did
   it succeed"; the OUTBOX answers "against what, and is it still current".

**Under `execution_intent: converge`, a producer preparation is stage K or stage L of the sequence in `saipen/CONVERGE.md`** -- that file owns the EE-before-QQ order and the rule that no main-source mutation may follow either of them.
