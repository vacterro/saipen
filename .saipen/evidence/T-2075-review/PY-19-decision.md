# T-2075 / PY-19 -- review decision

- package: PY-19 (identity sha256:361c2016f7667798c87cef28226a05cb65ee060315ab74bf176cfbefa46ab31c)
- package tree: f3dab073 (head dc39709c); OUTBOX status reviewed
- ticket state: T-2075 ## BLOCKED, blocker WAIT_USER_DECISION; owner saipen-cli, claimed 2026-11-16T16:53:33Z
- decision event: E-21520 (LOG DEC)

## Review outcome: the patch claim holds, no patch applied

PY-19 re-verified the byte-identical PY-15/PY-17/PY-18 GC serialization
patch at tree f3dab073: 3 of 4 fresh baseline samples reproduce the lost
checkpoint race, `git apply --check` passes on the then-current target bytes,
and the patched overlay passes 8/8 concurrent rounds plus the 63-test GC
suite. Core review accepted that result and, per the ticket's own verify
clause, applied no package patch during intake.

The tree then moved to cf7cd4a7; saipython re-verified at the live identity
as PY-20 (reviewed under T-2080, DEC E-21514). Integration of the patch
belongs to T-2062 inside the operator's 8.1.1 install/publication route.

## Closure: measured dead end, and the release-specific reason

T-2075's blocker names the mechanism: its `inherited_verified` closure needs
a committed release naming T-2062, and only the operator-authorized 8.1.1
install yields that release; T-2062 itself is blocked on the ZAICODE
operator-carrier chain. The full per-verb matrix is in
`.saipen/evidence/T-2080-review/PY-20-decision.md`. PROTOCOL.md sec. 4
accepts BLOCKED as terminal for a review ticket.

## Operator action

Two decisions, either order:
1. Authenticated ZAICODE ingress / fresh operator carrier (lifts T-2061 and
   the T-2062 dependency chain).
2. 8.1.1 generation install/publication staging (T-2058 gates A/B), which
   yields the committed release the closure mode requires.
See `.saipen/evidence/operator-decision-map.md`.
