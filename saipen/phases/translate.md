# Phase: TRANSLATE (triggered by `saipen translate`)

## Purpose

Build and maintain the translation bundle in a quarantined workspace, without
touching the main software.

## Entry

`saipen translate`. A parallel dedicated instance additionally requires the
project's `.saipen/` to already exist (`saipen set` has run) -- the same
precondition `saipen sub spawn` has. No `.saipen/` yet? Tell the user to run
`saipen set`; TRANSLATE is never a substitute for INIT.

## 1. Isolation

- "Exclusively inside `.saipen/saitranslate/`" scopes the *translation work* --
  source and assets. A same-agent phase switch (the common case) does NOT
  suspend normal bookkeeping: `.saipen/STATE.md`/`BOARD.md`/`LOG.md` are
  checkpointed as in every other phase (§ 1.5). Isolation and protocol
  discipline are not in tension.
- Never touch, modify or inject code into the main project files. The main
  project is a read-only reference for finding what needs translation.
- `.saipen/saitranslate/kitchen/` is this phase's scratch, separate from
  `.saipen/kitchen/` and never shared with it.
- **Legacy root-level `.saitranslate/`** (pre-v7.35.0): equivalent, MAY be
  migrated (`git mv .saitranslate .saipen/saitranslate`, one LOG line) at a
  convenient checkpoint. Never maintain both: `.saipen/saitranslate/` is
  authoritative, the root copy is stale, ticket its removal rather than
  guessing which is newer (MAINTENANCE.md § 2.1).
- **Running as a separate dedicated agent** (true parallelism, not a phase
  switch): do NOT write `phase: TRANSLATE` into the shared `.saipen/STATE.md`
  -- that stomps the main agent's active session (CORE.md § 1.4: one agent
  writes `.saipen/` at any instant). Keep progress in
  `.saipen/saitranslate/STATE.md`, same shape as Core's
  (`phase`/`task`/`next_action`/`agent`/`updated`), scoped to this build. The
  only contact with shared files is § 4's completion line, appended to the main
  `.saipen/LOG.md` when done -- nothing during the run. This is not read-only
  work; it writes freely inside its own sandbox, unlike
  `.saipen/extensions/subs/`'s subSaipen.
- **A parallel instance's cold start is not `BOOT.md`'s path.** `BOOT.md` step
  1 reads the SHARED `STATE.md`, which for a restarted parallel instance shows
  whatever phase the main agent is in and would send it to work on the main
  project instead of resuming its translation. If the operator told you to run
  as the parallel instance (`.saipen/STATE.md` will never tell you that), your
  continuation state is `.saipen/saitranslate/STATE.md`; the shared file is
  read-only reference for the § 3 freshness cross-check. The reverse mistake --
  a parallel instance writing its phase into the shared file -- already
  happened once; this is the other half of that failure mode.

## 2. Translation surface -- cover everything real, fabricate nothing

Read the actual project first. The real surface is **both** of these when they
exist, not an either/or:

- **(a) Documentation**: `README.md` and other top-level docs a user reads.
- **(b) Real in-app UI strings**, only if the software has any -- grep the real
  source for a genuine i18n/locale file already in use or real button/label
  text before building an `app.title`/`action.continue` JSON bundle.

Most SAIPEN-managed projects (protocols, CLIs, libraries, docs-first tools)
have (a) and not (b). Never fabricate the missing half to make the bundle look
more complete than the project is. (A real incident: a run once built 32
languages of `action.continue`-style strings for this repo, which has no app,
no settings screen and no such button.)

- **Docs**: translate what (a) covers and that has no hand-maintained
  per-language sibling. Never re-translate or overwrite a file the project
  maintains by hand per language (check for `<name>_XX.md`, e.g. this repo's
  `guides/`) -- note it as already covered. **The carve-out persists**: § 3's
  drift re-scan only watches surfaces TRANSLATE itself built in
  `.saipen/saitranslate/kitchen/`, so a hand-maintained sibling is never
  re-synced, first run or later. Keeping it in step with its English source is
  the job of whoever edits that source (a normal ticket).
- **Root README mirrors**: an explicit exception to that carve-out. The
  root-level mirrors (`README.ee.md`, `README.ded.md`, `README.ja.md`) MUST
  stay in exact sync with `README.md`; track their drift, update them, and
  preserve the language switcher at the top with Estonian highlighted. This is
  mandatory.
- **UI strings**: where (b) applies, build the JSON-bundle-per-locale system,
  sourced only from strings that actually exist.
- Either way the scope is the same: 32 languages, § 1's isolation, § 4's
  `.saipen/saitranslate/kitchen/` destination. This section changes only *what*
  is read, never where the output lives or how it is integrated.

**Six are the default set, always and everywhere: English, Russian, Estonian,
Ukrainian, Japanese, and the Дед voice.** Дед is not a garnish -- caveman+Дед
is SAIPEN's own voice, so its guide is as mandatory as English's. These MUST
exist and be current on every surface; the other 27 may lag. Without a named
default, "all 32" degrades to whichever ones a run reached, and nothing says
which absence is a defect. `tools/validate.py` holds all six to the
guide-opening contract.

**Who translates what -- a hard split, not a preference.** The main/Core agent
handles **English, Russian, Estonian and the `Дед` voice, and nothing else**.
Every other language is subSaipen work -- a dedicated `saitranslate`/`saiwiki`
instance on a deliberately small/cheap model, because bulk translation is
high-volume and low-complexity-per-unit. A Core agent finding 20-odd stale
languages MUST NOT grind through them "while it's here": ticket the remainder
for a dedicated instance and move on. This is scope, not capability -- Core may
still *verify* any language (byte-valid UTF-8, structure, spot-checks) and MUST
repair actual corruption anywhere, which is a correctness fix rather than a
translation pass.

The full list: *English, Russian, Estonian* (Core's own, with `Дед` below),
then *Japanese, Ukrainian, German, French, Spanish, Italian, Portuguese, Dutch,
Polish, Swedish, Danish, Finnish, Norwegian, Chinese, Korean, Thai, Vietnamese,
Arabic, Hebrew, Turkish, Hindi, Indonesian, Greek, Czech, Romanian, Hungarian,
Bulgarian, Slovak, Croatian* -- all 29 of those are subSaipen work, Japanese
included.

- **Flags:** associate a flag icon per language -- a language-picker table in a
  doc (this repo's `GUIDE.md`/`README.md`) for docs-first projects, live
  switching in Settings for UI-bearing ones. Unicode regional-indicator emoji
  (🇺🇸🇷🇺🇪🇪🇯🇵...) are the universal baseline; use drawn/SVG assets only
  where the platform supports image generation AND the project's existing icons
  are already that style. Match the project; do not invent an asset pipeline.
- **Дед voice:** build a `«Дед»` (angry-grandpa) localization. Core's own
  alongside EN/RU/ET: it is a *voice*, not a language, and getting it right is
  a STYLE.md judgment call (blunt, compressed, mocking, still factually exact)
  -- precisely what a cheap model flattens into neutral Russian.

## 3. Maintenance -- a running finger on the project's pulse

- EVERY run, not just the first, re-scans **both** § 2 surfaces against what is
  already built in `.saipen/saitranslate/kitchen/`. A new doc, an edited doc,
  or a new real UI string is drift the project accumulated while TRANSLATE was
  not watching.
- Translate exactly that drift across all 32 languages plus Дед. Do not blindly
  rebuild everything, and do not silently skip what changed: a stale
  translation beside updated source is worse than none, because nothing signals
  it has gone wrong. **Something signals it now, and keeping that signal
  honest is part of the pass.** Each locale README carries as its last line
  `<!-- source-digest: README.md sha256:<16 hex> -->` -- the digest of the
  English source it was translated FROM, with every `N.N.N` version string
  normalised to the literal `VERSION` first. After translating a locale,
  recompute that digest from the CURRENT `README.md` and write it into that
  locale's file -- for the locales you actually translated and no others,
  because stamping an untouched file is the lie this marker prevents.
  `tools/validate.py` WARNs on a mismatched digest and on a missing marker,
  naming the locales. Normalising the version out is what makes it usable: a
  release bumps the badge in all 65 locale files, so a digest including it
  would move every release and mean nothing -- the same reason commit dates
  cannot serve as this signal.
- Before calling it done, verify coverage is real: spot-check that everything
  identified in § 2 has a matching entry in every locale. A partial pass
  reported as 100% is worse than an honest partial report -- if something is
  missing, say so in the completion LOG line.

## 4. Completion / Exit

- A run intended for later collection is not complete until
  `.saipen/saitranslate/kitchen/OUTBOX.md` carries the PREPARE contract's exact
  fields: `status`, `producer`, `source_head`, `coverage`, `payload`,
  `verified`, `instructions`. Use `producer: saitranslate`. Only the full
  32-language plus Дед bundle over every real surface may say `status: ready`;
  partial work says `draft` or `blocked` and names the gap.
- LOG one normal Event Graph line per CORE.md § 1.2 -- `- DATE [E-###]
  [parent: E-###] RUN: translate -> done @SHORT-HASH` (this exact text after
  the taxonomy, not a free-text summary) -- then transition back to `DONE`.
- **Parallel dedicated instance (§ 1) only**: on completion delete your own
  `.saipen/saitranslate/STATE.md`. It is transient run-state; the bundle in
  `.saipen/saitranslate/kitchen/` stays (a future `ADD`/`PLAN` integrates it).
  No other phase reaps that cursor, so leaving it strands a stale STATE the
  next `saipen sub list`/scan trips over. A same-agent phase switch never wrote
  one, so this is a no-op there.
- Completion does NOT integrate the bundle. It sits in
  `.saipen/saitranslate/kitchen/` until a targeted `saipen collect
  saitranslate` consumes a `status: ready` handoff, creates/claims the Core
  ticket and routes it through the normal `VERIFY`/`REVIEW`/`SHIP` gates. No
  ready handoff means no main write.

## Failure / Blocked

Missing `.saipen/` -> tell the user to run `saipen set`; do not improvise INIT.
Both `.saitranslate/` locations present -> a conflict, not a merge: ticket the
stale root copy's removal. Coverage that cannot be completed -> `status:
draft`/`blocked` naming the gap, never a rounded-up "done".
