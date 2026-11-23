# Handoff — `Close-Ticket.ps1` (owner: the `_BZDECOMP` consumer project)

**This is not a repair of that script.** The script is not in the project it
closes tickets in, it was not executed, and its behaviour in a working state was
never observed. What follows is what was measured from outside, plus the exact
edits its owner needs.

## Ownership finding (CASE 17)

`Close-Ticket.ps1` exists only in agent scratchpads:

```
/v/_TEMP_/claude/V-----VAC---K---CODE--MISC--BZDECOMP/{065c31a8,4c51d23a,e9f0f98a}/scratchpad/
```

`find V:/___VAC/__K/__CODE/_MISC/_BZDECOMP -maxdepth 3 -iname "*Close*Ticket*"`
returns nothing. Two siblings exist in the same scratchpads: a 17-line
`Close-Tickets.ps1` (a thinner variant of the same sequence) and a 21-line
`close-tickets.sh`.

The scratchpad is a foreign location, the project is `_BZDECOMP`, and the
project has its own authority. No file in it was written.

## Blocker 1 — every mutating call is refused today

The script hardcodes a launcher from a DIFFERENT install than the project's own
STATE names:

```powershell
Set-Location 'V:\___VAC\__K\__CODE\_MISC\_BZDECOMP'
$sp = 'C:/Users/vac34/.agents/skills/saipen/bin/saipen.cmd'   # <- the wrong one
```

`_BZDECOMP/.saipen/STATE.md` says:

```
saipen_home: "V:/___VAC/__K/__CODE/_AI_STUFF_AGENTIC/_SAIPEN"
```

So every `claim`, `checkpoint`, `transition` and `ticket done` answers:

```
HOME_REQUIRED
home-dead: home-divergent: the RUNNING install is
  C:\Users\vac34\.agents\skills\saipen
  (install-v1:b29342bfc4dbb85d44c1f46ed171a00e6bc19744ff6f394bbef0cc4f065cf5a5)
but STATE.saipen_home names
  V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN
  (install-v1:a33673c718faebcd9b32eea37293bea644b4cde5162291d9c89baeb40f56bbfc)
```

Both installs report v8.1.0 and both have 171 engine modules, but their bytes
differ, and that divergence is exactly what the guard is for. The two installs
differ in four files:

```
tools/saipen_engine/core_unit.py
tools/test_next_action_deadlock.py
tools/validate.py
Only in tools: test_t1952_sandbox_points_at_itself.py
```

Measured cost of the refusal: ~250 ms per call, zero closure.

**Owner action (choose one):**

1. Point the script at the install the project names:
   `$sp = 'V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN\bin\saipen.cmd'`; or
2. Converge the project onto the `.agents` install with
   `saipen rebind-home --auto` in `_BZDECOMP` — but then the four file
   differences above become the protocol it runs under, so verify that is
   intended first.

Option 1 is the smaller change and does not alter the project's declared home.

## Blocker 2 — the suite is re-executed for a tree that did not move

The script's verification step:

```powershell
$null = Step @('test', 'suite', 'run', $Id)
```

The consumer's declared suite is `vrv/tools/Test-TacticalOrders.ps1` (16 tests).
Its 273 records show this call dominating every closure:

| window | n | median |
|---|---|---|
| Oct 15-19 | 87 | 1.5 s |
| Oct 28-29 | 35 | 451.0 s |

Grouped by recorded subject: 78 distinct trees, and repeated execution of the
same subject accounts for **19 675 s (5.5 h)** of 27 172 s total recorded suite
time. `86bb24cf8c38` alone was run 66 times for 4211 s where one 123.7 s run
answered every one of them.

That is the ten minutes. Not twelve CLI launches at 0.2 s each.

**Owner action:** add `--reuse` to that one line:

```powershell
$null = Step @('test', 'suite', 'run', $Id, '--reuse')
```

`--reuse` was added to SAIPEN by T-1953 and is engine-owned: it reuses only when
the newest admissible record of the DECLARED command PASSed the current tree's
bytes with a non-zero test count and no mid-run tree change. Otherwise it
executes and returns `reuse_withheld` naming the fact that failed. On a 30 s
fixture the same nine-call closure went 32.48 s -> 2.32 s.

**Requires** the project to run the install at `V:` (Blocker 1), because the
`.agents` install does not have `--reuse`.

Note the script uses `test suite run` + a prose PASS checkpoint, not the
`core_unit` full family. Those are two different gates with two different
records; `--reuse` applies to the declared suite only.

## Blocker 3 — a stale `Resolve-Source` writes evidence it did not verify

```powershell
function Resolve-Source {
    $receipt = ([regex]::Match($script:last, '"receipt":\s*"(SRC-\d+)"')).Groups[1].Value
    foreach ($clause in ([regex]::Matches($script:last, "$receipt`:(R\d+)") ...)) {
        $null = Step @('source','disp',$receipt,$clause,'IMPLEMENTED','--work',$Id,
                       '--evidence',$passEvent,'--verification',"$Verify -> PASS")
    }
}
```

`$script:last` is whatever the LAST call returned, and `Resolve-Source` is
invoked after `REVIEW`, after `SHIP`, and after `ticket done`. Only the first
invocation follows the PASS checkpoint. On the later ones `$script:last` is a
transition refusal, so `$receipt` is empty and the loop body never runs — benign,
but by accident. It also passes `--verification "$Verify -> PASS"` as a string
the operator supplied on the command line: that is a claim the script asserts,
not a fact the engine measured.

**Owner action:** capture `$receipt` immediately after the PASS checkpoint and
pass it in, rather than re-reading `$script:last`; and let the engine derive the
verification from the cited event instead of forwarding prose.

## What this handoff does NOT claim

- No timing for the script as a working whole. It never completed a closure
  here, so there is no end-to-end number for it.
- No claim that `--reuse` makes the suite faster. It does not.
- No claim about T-502 / T-490 specifically. Those ids appear in the
  scratchpads; this project's board is not their authority and I did not read
  their state as fact.
- No edit to `_BZDECOMP`, its `.saipen/`, its suite, or the scratchpad scripts.

## Suggested order

1. Fix `$sp` (Blocker 1) and confirm one closure completes end to end.
2. Measure that closure with the script's own timestamps — the shape is known,
   the working duration is not.
3. Add `--reuse` (Blocker 2) and re-measure the same ticket class.
4. Fix `Resolve-Source` (Blocker 3) separately; it is a correctness issue, not
   a latency one.
5. Investigate why the declared suite went 1.5 s -> 451 s for the same 16 tests.
   That is the consumer's own drift and the largest single term remaining.
