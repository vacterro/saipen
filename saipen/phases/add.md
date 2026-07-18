# Phase: ADD (Evolutionary Completer)

Activate this mode to systematically expand the software's capabilities. SAIPEN is evolutionary, not creative. Its purpose is to complete software, not reinvent it.

1. **Review:** Carefully review the current codebase. Understand the architecture, UI, and existing features.
2. **Evolve (Strict Decision Order):** Decide which capability to complete next by strictly evaluating this ladder top-to-bottom:
   1. **Missing bugfix?** → STOP. Transition back to `HUNT` or `BUILD`.
   2. **Missing complementary feature?** (Bold → Italic) → Add it.
   3. **Missing workflow step?** (Open → Save As) → Add it.
   4. **Missing UX consistency?** (Toolbar action without shortcut) → Add it.
   5. **Missing platform convention?** (Standard window controls) → Add it.
   6. **Minimal Delta satisfied?** (Change completes an existing pattern, does NOT start a new one) → Proceed.
   7. **Existing Design Language preserved?** (Extends current UI, does NOT create a new paradigm) → Proceed.
   8. **Product logically complete?** → Transition to `DONE`.
   
   Agent MUST NOT invent speculative, experimental, or unrelated features. Add small, solid improvements that naturally complete the product.

3. **Act:**
   - Pick exactly ONE obvious missing capability.
   - If the product is already mature and logically complete, **STOP**. Transition to `DONE` without hallucinating unnecessary features. Graceful completion is a successful outcome.
   - Otherwise, create a `TODO` ticket in `BOARD.md` describing the feature.
   - Transition to `PLAN` or `SCOUT` phase to begin immediate implementation.
   - Every addition MUST pass full `VERIFY` before another `HUNT` begins. Only if `HUNT` is clean may another `ADD` begin.
