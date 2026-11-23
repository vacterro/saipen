# FUTURE GATE — `ticket add` PREPENDS, SO A PLANNED WAVE LANDS IN REVERSE PRIORITY

Status: RECORDED FOLLOW-UP WORK / NOT AUTHORIZED FOR IMPLEMENTATION

Recorded: 2026-09-17 by a claude session bound to `__SAIMAIL__`
(lineage `lineage-3172dbca95fc4945955bdee3acff8d75`), observed live against
installed protocol `8.0.1`. Third and smallest of three records from the same
bind. Not a claim that anything is fixed; not usable as coverage evidence.

## DEFECT — PLANNING ORDER IS INVERTED BY THE ONLY VERB THAT CREATES TICKETS (P2)

`CORE.md` `PICK-01`: "choose the topmost workable line. **Board order is
priority**". There is no priority sort; position *is* the priority.

`saipen ticket add` inserts at the top of `## TODO`. Therefore a wave added in
plan order comes out in exactly reverse plan order.

Reproduced: nine tickets added in dependency order, T-1 (parser, P1) first
through T-9 (cost benchmark, P3) last. Resulting board:

```
## TODO
- [ ] T-9 [P3] Cost benchmark …
- [ ] T-8 [P3] SAINOTE renderer …
…
- [ ] T-1 [P1] SAILANG v0 record parser …
```

`saipen continue --json` then returns:

```
"action": "PHASE SCOUT T-9", "ticket": "T-9", "reason": "start"
```

The router sends the next seat to benchmark code that the bottom ticket has
not written yet. The `[P3]` / `[P1]` tags rendered on the rows are decoration:
they are not the ordering authority and nothing consults them.

## WHY THE REMEDIES DO NOT COVER IT

- `saipen claim <T-###> --explicit` overrides the pick and honestly logs the
  stepped-over ticket. It fixes one claim, not the board, so every subsequent
  pick is wrong again and every correct claim costs a step-over event. The LOG
  fills with overrides that record an ordering mistake nobody made.
- `saipen ticket retire` cannot be used to re-lay a board:

```
"code": "RETIREMENT_REASON_UNKNOWN",
"message": "reason '' is outside the registered set MISROUTED_PROJECT_BINDING; retirement never accepts a free-text reason"
```

- Hand-editing `BOARD.md` is the one path `OPS.md` 4a forbids.

That combination is the shape `CORE.md` itself names as a defect class: "A
refusal that names a remedy no surface exposes drives the operator to
hand-edit BOARD.md". Here there is not even a refusal — the board is accepted,
valid, and silently mis-prioritised.

The agent-facing consequence is the one that matters: an agent that plans a
correct dependency order and enters it faithfully produces a board that
executes it backwards, and nothing in the system says so.

## BOUNDED FOLLOW-UP OPTION

Any one of these, not all three:

1. `ticket add --after <T-###>` / `--bottom`, so a wave can be entered in plan
   order. Smallest change; default stays prepend.
2. A `ticket move <T-###> <position|--after T-###>` verb, journaled like any
   other mutation, closing the hand-edit pressure properly.
3. Make `add` accept an ordered batch (one call, N tickets, order preserved),
   which is the actual shape of the planning operation that triggers this.

Required hostile controls:

- Nine tickets entered in plan order are pickable in plan order; the red
  control on current code shows `continue` returning the last-added ticket.
- Ordering remains a journaled operation: no verb writes BOARD rows outside
  the canonical path, and hand-edit detection stays intact.
- `PICK-01` semantics unchanged: topmost workable still wins. This is about
  how a row reaches the top, not about how the pick reads the board.

NON-GOALS: do not add a priority-sorting router (board order is the contract,
and a second ordering authority would be worse than the current one); do not
widen the retirement reason set to permit re-laying a board.

## ORIGINATING MISSION

First ticket wave of `__SAIMAIL__`, 2026-09-17. The board is being left as-is,
inverted and valid, as an in-the-wild specimen. The fix belongs to the protocol
tree, a different repository than the bound project.
