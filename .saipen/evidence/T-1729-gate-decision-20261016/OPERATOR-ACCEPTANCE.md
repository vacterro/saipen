# Prepared human acceptance — SRC-228:R019

Status: **PREPARED, UNAPPROVED**. These files and fixture creation grant no
authority. The fixture is synthetic and disposable, outside SAITULS. No
authority Source has been captured for it and no approval has been applied.

Project: `V:\_TEMP_\t1324-blocker-42_ghqn4`; actor: `tester`.
Exact lineage, gate version, fields and expiry are in
`operator-decision-DRAFT.json`; `operator-fixture.json` preserves the binding.
The draft expires on **2026-10-18 at 10:18:59 UTC**. Regenerate the preview if
the fixture changes or the deadline passes; never replay an obsolete scope.

An operator must inspect the draft and supply their own explicit statement
accepting only this fixture's synthetic limitation, through the existing
independent operator-input carrier. The current agent must not install a task
file/digest environment variable to authenticate its own generated draft.
The ordinary chat instruction `cc all` is not the missing scoped decision.

Under that original witnessed operator input, the exact native sequence is:

```powershell
saipen --project-root 'V:\_TEMP_\t1324-blocker-42_ghqn4' --agent tester authority capture --file '<human-authored-decision.json>' --json
saipen --project-root 'V:\_TEMP_\t1324-blocker-42_ghqn4' --agent tester recover resolve-blocker SRC-N --json
saipen --project-root 'V:\_TEMP_\t1324-blocker-42_ghqn4' --agent tester continue --json
saipen --project-root 'V:\_TEMP_\t1324-blocker-42_ghqn4' --agent tester recover --json
saipen --project-root 'V:\_TEMP_\t1324-blocker-42_ghqn4' --agent tester continue --json
```

Replace SRC-N with the capture's actual receipt. Preserve original provenance
and output, including a fresh-process restart. Expected: only the fixture's
named blocker/WAIT resolves, SCOUT T-001 remains the admitted action after
restart/reconciliation, the approval replay writes nothing, and an
unwitnessed decision is refused. Unit harness witnesses do not satisfy this
human-origin acceptance criterion.

No SAITULS approval, historical E-3009 upgrade, held-ticket dispatch or
publication is part of this acceptance.
