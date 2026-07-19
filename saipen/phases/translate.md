# Phase: TRANSLATE (triggered by `saipen translate`)

Deep, isolated translation preparation system. This phase runs in a strictly quarantined environment and focuses exclusively on building a massive translation bundle without touching the main software.

1. **Isolation Rule:**
   - You MUST operate EXCLUSIVELY inside `.saipen/kitchen/translation/`.
   - You MUST NOT touch, modify, or inject code into the main project files during this phase. Treat this as a background job for a separate, simultaneous agent.

2. **Core Translation Build:**
   - Establish a robust translation system infrastructure (e.g., JSON bundles, structured locales).
   - You MUST translate the software strings into the following 22 languages: 
     *English, Russian, Ukrainian, German, French, Spanish, Italian, Portuguese, Dutch, Polish, Swedish, Danish, Finnish, Norwegian, Japanese, Chinese, Korean, Thai, Vietnamese, Arabic, Hebrew, Estonian*.
   - **UI Assets:** For each language, you MUST associate or prepare a drawn flag icon and the configuration for live-switching in Settings.
   - **Bonus Voice:** You MUST also build a `«Дед»` (angry-grandpa) voice localization.

3. **Maintenance and Update:**
   - If the core translation system already exists, compare it against the latest main software strings.
   - Update missing translations across all 22 languages and the bonus voice to ensure 100% coverage.

4. **Completion:**
   - Once the translation bundle is fully built, validated, and up-to-date, `RUN: translate -> done`, log the actions, and transition the phase back to `DONE`. 
   - The bundle will sit safely in the `kitchen` until a future `ADD` phase formally integrates it into the software.
