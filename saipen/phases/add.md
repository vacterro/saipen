# Phase: ADD (Evolutionary Completer)

Activate this mode to systematically expand the software's capabilities. SAIPEN is evolutionary, not creative. Its purpose is to complete software, not reinvent it.

1. **Review:** Carefully review the current codebase. Understand the architecture, UI, and existing features.
2. **Evolve:** Decide which capability to complete next based on the following absolute rules:
   - **Complementary Functionality:** If Bold exists, add Italic. If Copy exists, add Paste.
   - **Standard Workflows:** If Open exists, add Save As.
   - **UX Consistency:** If a toolbar action exists without a keyboard shortcut, add the shortcut.
   - **Platform Conventions:** Ensure the application behaves as expected for its platform.
   - **Minimal Delta:** `ADD` MUST choose the smallest change that maximally improves product completeness. A change MUST complete an existing pattern rather than start a new one (e.g. add Italic, do NOT add Markdown Export).
   - **Existing Design Language:** `ADD` MUST extend an existing design language before introducing a new one. (e.g. add Italic to the existing Toolbar, do NOT create a new "Formatting Hub" side-panel).
   
   Agent MUST NOT invent speculative, experimental, or unrelated features. Add small, solid improvements that naturally complete the product.

3. **Act:**
   - Pick exactly ONE obvious missing capability.
   - If the product is already mature and logically complete, **STOP**. Transition to `DONE` without hallucinating unnecessary features. Graceful completion is a successful outcome.
   - Otherwise, create a `TODO` ticket in `BOARD.md` describing the feature.
   - Transition to `PLAN` or `SCOUT` phase to begin immediate implementation.
   - Every addition MUST pass full `VERIFY` before another `HUNT` begins. Only if `HUNT` is clean may another `ADD` begin.
