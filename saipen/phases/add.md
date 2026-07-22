# Phase: ADD (Evolutionary Completer)

Activate this mode to systematically expand the software's capabilities. SAIPEN is evolutionary, not creative. Its purpose is to complete software, not reinvent it.

1. **Review:** Carefully review the current codebase. Understand the architecture, UI, and existing features.
2. **Evolve:** Agent MUST NOT invent speculative, experimental, or unrelated features. Agent MUST evaluate additions strictly using the following logic:

   ```pseudocode
   FOR priority IN [
     "bugfix", 
     "complementary_feature (Bold->Italic)", 
     "workflow_step (Open->Save_As)", 
     "ux_consistency", 
     "platform_convention"
   ]:
     IF exists(priority):
       IF priority == "bugfix":
         TICKET(priority)
         RETURN SCOUT
       IF satisfies(minimal_delta) AND satisfies(existing_design_language):
         TICKET(priority)
         RETURN BUILD
       ELSE:
         TICKET(priority)
         RETURN PLAN_or_SCOUT
   
   RETURN DONE
   ```

   Two implementation paths come out of this -- never a third:
   1. **Direct minimal implementation**: satisfies both `minimal_delta`
      and `existing_design_language` -> ticket it, place in `TODO`, and `RETURN BUILD` (skip planning and scouting, just build it now).
   2. **Planned implementation**: a real gap exists but isn't obviously
      minimal or isn't obviously in the existing design language ->
      ticket it, `RETURN PLAN` or `SCOUT` (step 3 below), never build
      it directly just because a priority slot matched. Without this
      `ELSE`, a genuine but non-minimal opportunity silently fell through
      to `RETURN DONE` -- declaring the product mature when it wasn't.

   `bugfix -> TICKET(priority); RETURN SCOUT` means ADD does not improvise the fix inline. It formally tickets the bug and enters the standard execution pipeline. Bouncing back to `HUNT` is illegal here because `HUNT` only scans 6 mechanical signals -- if `HUNT` didn't catch the bug on its own pass, sending `ADD` back to `HUNT` creates an infinite loop.

3. **Act:**
   - Pick exactly ONE obvious missing capability.
   - If the product is already mature and logically complete, **STOP**.
     Transition to `DONE` without hallucinating unnecessary features --
     graceful completion is a successful outcome. `goal_mode: true`? This
     IS the mature-exit condition RFC § 2.4 defines: set `goal_mode:
     false`, clear `goal_waves`/`goal_tickets`, write the final report
     (tickets done/verified/shipped vs blocked, pre-existing backlog vs
     found along the way), then STATE -> `DONE`.
   - Otherwise, create a `TODO` ticket in `BOARD.md` describing the
     feature. Transition to `PLAN` or `SCOUT` phase to begin immediate
     implementation.
   - `goal_mode: true` and this wasn't the mature-exit case above? Either
     branch still completes this HUNT->ADD cycle -- increment
     `goal_waves` by 1 and checkpoint STATE (RFC § 2.4). Hits the
     3-`goal_waves`/20-`goal_tickets` cap? STOP here instead of
     continuing -- full BOARD/STATE checkpoint, report progress, wait for
     the user to re-invoke `saipen goal`.

4. **The Industrial Completion Rule:**
   - When the user requests one step of a well-known user workflow, you SHOULD evaluate what else is needed to make the feature industrially complete -- a judgment call, not mechanical (RFC § 2.3).
   - You MUST implement the *minimal coherent set* (e.g., adding "Cancel" and "Save" if asked for "Apply").
   - The smallest complete solution wins. Do not build massive epics (e.g., do not add Cloud Sync when asked for Export).
   - Complete before you extend: finish the requested workflow before proposing a different one (e.g., "Login" implies "Logout" — not OAuth or SSO). The agent SHOULD preserve user expectations before introducing new capabilities.

5. **Baseline Architectural Constraints** (apply to every `ADD`, whether or
   not the Industrial Completion Rule is in play):
   - *Session Persistence*: state the user can see or set (window position,
     size, toggles, themes) MUST save and restore between sessions.
   - *No Hardcoding*: prefer user-editable configuration (keybinds,
     controls, templates) over values baked into code.

6. Every addition MUST pass full `VERIFY` before another `HUNT` begins. Only if `HUNT` is clean may another `ADD` begin.
