# Phase: TRANSLATE (triggered by `saipen translate`)

Deep, isolated translation preparation system. This phase runs in a strictly quarantined environment and focuses exclusively on building a massive translation bundle without touching the main software.

1. **Isolation Rule:**
   - "Exclusively inside `.saitranslate/`" scopes the *translation work itself* -- the software's source and assets. When the same agent already running the project transitions into this phase (the common case -- phase-switching, not parallelism), it does NOT suspend normal SAIPEN bookkeeping: `.saipen/STATE.md`/`BOARD.md`/`LOG.md` still get checkpointed exactly as every other phase requires (§ 1.5). Isolation and protocol discipline are not in tension.
   - You MUST NOT touch, modify, or inject code into the main project files during this phase. Treat the main project strictly as a read-only reference to understand what strings need translation.
   - `.saitranslate/` has its own `kitchen/` for scratch and half-finished work -- separate from `.saipen/kitchen/`, never shared with it. Nothing from this phase's scratch work belongs in the main project's kitchen.
   - **Running as a separate, dedicated agent** (sent to build the translation bundle while the main agent keeps building elsewhere -- true parallelism, not a phase switch): do NOT write `phase: TRANSLATE` into the shared `.saipen/STATE.md` -- that stomps on whatever the main agent's own session actually has active (RFC § 1.4's concurrency boundary: one agent writes `.saipen/` at any instant). Keep progress in `.saitranslate/STATE.md` instead -- same shape as Core's own `STATE.md` (`phase`/`task`/`next_action`/`agent`/`updated`), scoped to this build, nobody else's business to touch. The only contact with shared files is the completion line step 4 already requires -- append it to the *main* `.saipen/LOG.md` when done, nothing more, nothing during the run. This isn't read-only work (it writes plenty, just confined to `.saitranslate/`) -- don't confuse it with `extensions/subs/`'s subSaipen, which is read-only toward the whole project and never writes anywhere real. TRANSLATE-in-parallel writes freely inside its own sandbox; it just never touches the *shared* bookkeeping mid-run.

2. **Determine the real translation surface first -- never fabricate:**
   - Read the actual project before deciding what to translate. Most SAIPEN-managed projects are protocols, CLIs, libraries, or docs-first tools with no in-app UI at all -- for these, the real translatable surface is the project's own documentation (`README.md`, other top-level docs a user actually reads), not invented UI strings for a settings screen that doesn't exist. Grep the real source for actual UI-string patterns (an existing i18n/locale file already in use, real button/label text) before building an `app.title`/`action.continue`-style JSON bundle -- if nothing like that exists in the project, don't invent it. (A real incident: an earlier run built exactly such a bundle for this repo -- SAIPEN has no app, no settings screen, no `action.continue` button anywhere -- 32 languages of fabricated strings that translated nothing real.)
   - **Docs-first projects**: translate `README.md` and other top-level docs that don't already have a hand-maintained per-language sibling. Never re-translate or overwrite a file the project already maintains by hand per language (check for an existing `<name>_XX.md`-style file first, e.g. this repo's own `guides/`) -- note it as already covered instead of duplicating or clobbering curated work.
   - **UI-bearing projects**: build the JSON-bundle-per-locale system as before, sourced only from strings that actually exist in the software.
   - Either way, same scope as before: 32 languages, **prioritizing English, Russian, Estonian, and Japanese**, same isolation rule (§ 1), same `.saitranslate/kitchen/` destination (§ 4) -- this section only changes *what* gets read to produce the bundle, never where it lives or how it gets integrated.
   - The full list is: *English, Russian, Estonian, Japanese, Ukrainian, German, French, Spanish, Italian, Portuguese, Dutch, Polish, Swedish, Danish, Finnish, Norwegian, Chinese, Korean, Thai, Vietnamese, Arabic, Hebrew, Turkish, Hindi, Indonesian, Greek, Czech, Romanian, Hungarian, Bulgarian, Slovak, Croatian*.
   - **Flags:** For each language, associate a flag icon -- a language-picker table in a doc (this repo's own `GUIDE.md`/`README.md`) for docs-first projects, live-switching config in Settings for UI-bearing ones. Unicode regional-indicator flag emoji (🇺🇸🇷🇺🇪🇪🇯🇵...) are the universal baseline every agent can produce without an image tool; use drawn/SVG assets only if the platform supports image generation and the project's existing icons are already that style -- match the project, don't invent a new asset pipeline.
   - **Bonus Voice:** You MUST also build a `«Дед»` (angry-grandpa) voice localization.

3. **Maintenance and Update:**
   - If the core translation system already exists, compare it against the latest main software strings.
   - Update missing translations across all 32 languages and the bonus voice to ensure 100% coverage.

4. **Completion:**
   - Once the translation bundle is fully built, validated, and up-to-date,
     LOG one normal Event Graph line per RFC § 1.2 -- `- DATE [E-###]
     [parent: E-###] RUN: translate -> done @SHORT-HASH` (this exact text
     after the taxonomy, not a free-text summary) -- then transition the
     phase back to `DONE`.
   - TRANSLATE completion does NOT integrate the bundle into the main
     software -- the bundle sits safely in `.saitranslate/kitchen/` until
     a future `ADD`/`PLAN` ticket formally integrates it, through the
     normal `VERIFY`/`REVIEW`/`SHIP` gates like any other change, never as
     a side effect of TRANSLATE itself.
