# Phase: ADD (Evolutionary Completer)

Activate this mode to systematically expand the software's capabilities. SAIPEN is evolutionary, not creative. Its purpose is to complete software, not reinvent it.

**Never entered under `execution_intent: converge`** (T-539): a converge run never reaches this phase -- a clean `HUNT` under converge routes to `CLEAN` or the closure sequence per `saipen/CONVERGE.md` (stages F/I, referenced not restated), and CONVERGE.md stage C forbids `ADD` outright because invention is the one thing convergence cannot terminate. Everything below applies only to the `normal`/`goal` path.

A section of prose is an addition like any other, so § 1.1's gate applies before § 2.2's ladder: a new section names the defect class it eliminates, or it does not get written.

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
         CLAIM(ticket)
         RETURN BUILD
       ELSE:
         TICKET(priority)
         RETURN PLAN_or_SCOUT
   
   RETURN DONE
   ```

   Two implementation paths come out of this -- never a third:
   1. **Direct minimal implementation**: satisfies both `minimal_delta`
      and `existing_design_language` -> ticket it, then claim it immediately
      (`TODO` -> `DOING`, checkbox `[/]`, `owner:`/`claim_time:` set, same
      as `phases/scout.md`'s own claim step) before `RETURN BUILD` -- skip
      planning and scouting, just build it now, but never leave the ticket
      sitting unclaimed in `TODO` while `STATE.phase` has already moved to
      `BUILD`.
   2. **Planned implementation**: a real gap exists but isn't obviously
      minimal or isn't obviously in the existing design language ->
      ticket it, `RETURN PLAN` or `SCOUT` (step 3 below), never build
      it directly just because a priority slot matched. **Which of the two**
      is the same size judgment `phases/plan.md`'s own size gate makes, not
      a coin flip: the ticket's next step is already concrete and the work
      is small (roughly its `<=2 files + obvious change` bar) -> `SCOUT`,
      since there is nothing left to plan; it needs design, dependency
      ordering, or research before anyone can start -> `PLAN`. Unsure ->
      `PLAN`, the cheaper mistake (a redundant planning pass costs one
      short analysis; skipping a needed one costs a wrong build). Without this
      `ELSE`, a genuine but non-minimal opportunity silently fell through
      to `RETURN DONE` -- declaring the product mature when it wasn't.

   `bugfix -> TICKET(priority); RETURN SCOUT` means ADD does not improvise the fix inline. It formally tickets the bug and enters the standard execution pipeline. Bouncing back to `HUNT` is illegal here because `HUNT` only scans 6 mechanical signals -- if `HUNT` didn't catch the bug on its own pass, sending `ADD` back to `HUNT` creates an infinite loop.

3. **Act:**
   - Pick exactly ONE obvious missing capability.
   - If the product is already mature and logically complete, **STOP**.
     Transition to `DONE` without hallucinating unnecessary features --
      graceful completion is a successful outcome. `execution_intent: goal`? This
      IS the mature-exit condition MAINTENANCE.md §2.4 defines: clear the goal
      intent and clear `goal_waves`/`goal_tickets`, write the final report
     (tickets done/verified/shipped vs blocked, pre-existing backlog vs
     found along the way), then STATE -> `DONE`.
   - Otherwise, ticket it and proceed by the two implementation paths
     above -- not `PLAN`/`SCOUT` unconditionally: a minimal-delta ticket in
     the existing design language is claimed (`[/]`, `owner:`/`claim_time:`,
     `TODO` -> `DOING`) and goes straight to `BUILD`; anything else goes to
     `PLAN` or `SCOUT`. Never leave a ticket unclaimed in `TODO` while
     `STATE.phase` has already moved to `BUILD`.
   - `execution_intent: goal` and this wasn't the mature-exit case above? Either
     branch still completes this HUNT->ADD cycle -- increment
     `goal_waves` by 1, **write the identifiable LOG line MAINTENANCE.md §2.4 requires
     for it -- `DEC: goal_waves N->M`, that exact text after the taxonomy** --
     and checkpoint STATE. The LOG line is not decoration: § 1.5's Recovery
     rebuilds the counters after a crash by *counting these lines*, so a bump
     recorded only in `STATE.md` is a bump Recovery cannot find if `STATE.md`
     is the file that got lost. Until v7.87.0 this doc named the increment and
     never the line, in the one place a wave is ever counted -- meaning the
     safety valve silently lost its count on exactly the long unattended runs
     it exists to protect. This is the ONE
     place this cycle's wave gets counted: if this branch was `RETURN PLAN`,
     the `PLAN` run that follows MUST NOT increment `goal_waves` again for
     the same cycle (`phases/plan.md`'s own carve-out) -- otherwise one
     `HUNT`->`ADD`->`PLAN` chain double-counts. Hits the
     3-`goal_waves`/20-`goal_tickets` cap? STOP here instead of
     continuing -- full BOARD/STATE checkpoint, report progress, wait for
     the user to re-invoke `cc` to re-authorize and continue.

4. **The Industrial Completion Rule:**
   - When the user requests one step of a well-known user workflow, you SHOULD evaluate what else is needed to make the feature industrially complete -- a judgment call, not mechanical (MAINTENANCE.md §2.3).
   - You MUST implement the *minimal coherent set* (e.g., adding "Cancel" and "Save" if asked for "Apply").
   - The smallest complete solution wins. Do not build massive epics (e.g., do not add Cloud Sync when asked for Export).
   - Complete before you extend: finish the requested workflow before proposing a different one (e.g., "Login" implies "Logout" — not OAuth or SSO). The agent SHOULD preserve user expectations before introducing new capabilities.

5. **Baseline Architectural Constraints** (apply to every `ADD`, whether or
   not the Industrial Completion Rule is in play):
   - *Session Persistence*: state the user can see or set (window position,
     size, toggles, themes) MUST save and restore between sessions.
   - *No Hardcoding*: prefer user-editable configuration (keybinds,
     controls, templates) over values baked into code.

6. Tickets ADD creates follow the normal Core flow from here -- `BUILD -> VERIFY -> REVIEW -> SHIP -> DONE` (CORE.md §1.6) -- ADD itself never implements anything directly or short-circuits past `BUILD`. `ADD` does not run on a fixed per-ticket cadence: it begins again only after a clean `HUNT` (MAINTENANCE.md §2.1), whenever that next occurs.

7. **Before leaving ADD, LOG what it decided.** Every other phase doc ends
   with this; `add.md` did not until v7.87.0, which is how the `goal_waves`
   line above went unwritten for so long. One Event Graph line per CORE.md §1.2,
   whichever applies:
   - ticketed and claimed a minimal-delta change -> `RUN: add -> T-### <what>`
   - ticketed for planning instead -> `RUN: add -> T-### <what>, RETURN PLAN`
   - concluded mature -> `DEC: add -> mature, intent normal` plus the final
     report § 2.4 requires
   - found nothing and the board was already empty -> say exactly that;
     CORE.md §1.11 requires a session to leave a trace, and "ADD ran and found
     nothing" is a real finding worth recording, not silence.
   Then checkpoint per § 1.5 (LOG -> `BOARD.md` -> `STATE.md`) and re-read the
   `STATE.md` you wrote. ADD creates and claims tickets; an unlogged claim is
   how a ticket ends up owned by nobody.
