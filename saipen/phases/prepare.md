# Phase: PREPARE

Entered by explicit user command: `saipen prepare [producer]`.

This phase is primarily used by specialized roles and subSaipens (e.g., `saitranslate`, `saiwiki`, `saihunt`) to finalize their work and package it for the next agent (usually the main project agent) to consume. A named producer scopes one complete deliverable; it is never permission to substitute a quick scan.

1. **Freshness Check**: Before preparing the result, verify that your findings or outputs are still valid against the *current* project HEAD. If the main project has moved and invalidated your work, update your work first. The payload MUST be fresh.
2. **Core Result Formatting**: Assemble your final artifacts (code, translations, documentation, or hunt reports). Ensure they are complete and structurally sound.
3. **Comprehensive Instructions**: Write a clear, step-by-step guide for the *next agent* explaining exactly how to inject or use this core result in the main software. Assume the next agent has zero context about your internal process.
4. **Delivery**:
   - Every collectable handoff MUST include these fields: `status`, `producer`, `source_head`, `coverage`, `payload`, `verified`, and `instructions`. `status: ready` is legal only when coverage is complete, the source HEAD is current, producer-side checks passed, and the payload plus injection instructions are executable without guessing. Otherwise write `status: draft` or `status: blocked` and state the gap.
   - If you are running as a subSaipen (RFC § 1.9), write the combined result and instructions into your `kitchen/OUTBOX.md`, and mark your current ticket as `[x]` in `## DONE` only when the handoff is ready.
   - `saipen prepare saitranslate` first executes the complete TRANSLATE contract over every real documentation and in-app UI surface, then writes `.saipen/saitranslate/kitchen/OUTBOX.md`. Its `coverage` enumerates every discovered source surface and every required locale; its `payload` enumerates the exact files to integrate. It MUST NOT touch main-project files.
   - `saipen prepare saiwiki` spawns or adopts `saiwiki` if needed, completes the current wiki maintenance scope, then writes `.saipen/extensions/subs/saiwiki/kitchen/OUTBOX.md`. Its `coverage` enumerates every maintained page and relevant source invariant; its `payload` enumerates the exact pages to integrate. It MUST NOT touch the main project or wiki remote.
   - An unqualified main-project preparation may place a non-collectable package in `.saipen/kitchen/`; it MUST NOT impersonate a named producer's ready handoff.
5. **Isolation**: PREPARE packages only. It MUST NOT integrate the payload into the target, modify a target remote, commit, tag, or push. Those belong to `saipen collect <producer>` followed by the normal Core gates and an explicit SHIP chain.
6. **Completion**: LOG one Event Graph line per RFC § 1.2 -- `- DATE
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
