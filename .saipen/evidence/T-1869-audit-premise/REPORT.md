# T-1869 / SRC-298 — adjudication of `audit/SAIHANDOFF_FASTPROMPTER_AUTHORITY_BLOCKED.md`

MODE of the audited layer: **AUTHORITY BLOCKED**. It performs no implementation and
exists to record one claim: that FastPrompter's bounded-run valve cannot be cleared
from a ZAICODE session, so the operator must move to an OpenCode host.

That claim has two halves, and this Work separates them because only one is still true.

## What was true when the audit was written

`audit/...AUTHORITY_BLOCKED.md` is dated 2026-10-23 and was ingested at
`2026-10-23T08:48Z`. At that moment the repository held no ZAICODE adapter at all:

```
$ git cat-file -e HEAD:extensions/adapters/zaicode/saipen-guard.py
fatal: path 'extensions/adapters/zaicode/saipen-guard.py' exists on disk, but not in 'HEAD'
$ git status --porcelain -- extensions/adapters/zaicode/
?? extensions/adapters/zaicode/
```

The audit's section 02 says "the only host adapter present is
`extensions/adapters/opencode/saipen-guard.js` (no ZCode adapter exists)". That was
an accurate observation, not an error. Nothing here disputes it.

## What is false now

T-1868 (this run) built and installed the missing adapter, and the live
configuration dispatches it on the operator's own prompt event. Measured:

```
repo adapter : True 7772 bf9e9a900c86502c
installed    : True 7772 bf9e9a900c86502c
byte-identical: True
config hooks.enabled: True
UserPromptSubmit entries: 1
  cmd: ...\Python311\python.exe
  args[1]==bootstrap: True
  script: C:\Users\vac34\.zcode\hooks\saipen-guard.py
```

So the audit's *exclusive* unblock route — "Option A (recommended): launch an
OpenCode host" — is no longer the only route, and the stronger statement in its
section 02, that `cc` from this host "cannot" renew the budget because the host
has no adapter, is disproven. ZAICODE is now a carrier-capable host.

## The part that had to be re-measured rather than assumed

The hook binds the project from the **event's `cwd`**, not from its own
`--saipen-root` argument. That matters because every operator session in this
workspace runs a hook configured with `--saipen-root` pointing at the protocol
home. If the hook had bound that argument, an operator `cc` inside a
FastPrompter session would have reauthorized the *protocol home* and left
FastPrompter trapped — which would have preserved the audit's conclusion by a
different mechanism.

Measured against the live installed hook, with the event `cwd` set to the
FastPrompter project and `--saipen-root` left at the protocol home:

```
stdout: {"ok": true, "ingress_id": "ing-896e59f957df5fb2",
         "destination_op": "continue", "consumed": true, "sealed": false}
FastPrompter cache records: 1
   ing-896e59f957df5fb2 'cc' destination_op= continue sealed= False
records landed in the pinned protocol home: 0
```

The envelope lands in the event's project. A ZAICODE prompt inside FastPrompter
delivers to FastPrompter. (`sealed: false` here is correct and is the next
section; the probe record was retired with `consume_host_ingress`, leaving the
project at 0 active ingress records — not deleted by hand.)

## What this Work cannot prove, and does not claim

A seal is minted by the separated broker only for the installed hook or the
engine it started. A shell tool call is neither, by design:

```
code: BROKER_CLIENT_NOT_AUTHENTICATED
detail: the connecting process is under the host application but is not the
        installed host hook or the engine it started (a shell tool call is not a hook)
```

The host *is* recognized in that ancestry (`host_images: ['ZAICODE.exe']`, with
`ZAICODE.exe` processes present in the chain), but the connecting process is not
the hook, so no origin is minted. This is the correct refusal and it is the same
boundary that T-1859/SRC-291 records as a LIVE outcome: **only a genuine operator
turn through the running host can produce a sealed origin.** Test doubles and
source-only changes cannot, and this Work does not manufacture one.

Therefore the honest state of the audit's subject is:

- The transport defect that made ZAICODE unable to deliver a carrier is cured and
  proven red→green under T-1868.
- Whether a live ZAICODE turn actually seals on this machine is unproven from
  inside a shell, and remains T-1859's owned clause. It is not claimed here.
- FastPrompter's valve is still tripped (measured: 3 waves / 39 tickets), which
  is the valve working as designed rather than a defect. Its remaining queue is
  owned by FastPrompter's own board, which has advanced to `phase: DONE` with 39
  goal tickets since the audit was written — evidence that its valve has already
  been renewed repeatedly.

## Why the finding closes as invalidated rather than as repaired

The audit is another agent's report about a blocker it could not clear. This Work
neither rewrites that report nor pretends the blocker was imaginary. It records
that the report's blocking premise — "no ZCode adapter exists, therefore only
OpenCode can renew" — no longer holds, and that the operator's obligation shrank
from "switch hosts" to "send the same `cc` you always send, in the session you
already have". That is the whole deliverable; the residual LIVE seal belongs to
the Work that already owns it.

## Files

- `measurements.log` — the six measurements above, regenerated from the live
  tree by a single script (M1 adapter/config identity, M2 hook binding, M3
  envelope destination, M4 seal refusal, M5 FastPrompter counters, M6 live
  refusal).
