# Foreign-delta inquest -- injector/runtime provenance change of 2026-09-17 18:04Z

Scope: three tracked product files found modified in the working tree after
E-7006 and before the T21-49-50 snapshot, with no SAIPEN LOG event and no
owning SAIPEN ticket:

    bootstrap/inject.ps1
    bootstrap/inject.sh
    tools/saipen_engine/runtime_bootstrap.py

Method: git diff and object hashes, file mtimes, the OpenCode session store
(`~/.local/share/opencode/opencode.db`, read-only), the Claude Code project
store (`~/.claude/projects`, `~/.claude/file-history`), the Antigravity
conversation store (`~/.gemini/antigravity/conversations`, read-only), and the
`~/.gemini` / `~/.agents` install targets. No future Inquest framework was
implemented; its reasoning was applied by hand, and all probes live in
`V:\_TEMP_\opencode\` (`opencode_inquest.py`, `opencode_writers.py`,
`antigravity_probe.py`, `antigravity_context.py`, `claude_scan.py`).

## 1. Exact delta

    bootstrap/inject.ps1                     blob 7fdcdacae6eecbd96a560dd1294305d397896435
    bootstrap/inject.sh                      blob 36c2882ecffeb35cef13c270f6d6b2bd21fa6ce0
    tools/saipen_engine/runtime_bootstrap.py blob f294213554e0e2bc6e2a5c342820a33c67c5e164

Full diff: `foreign-delta.diff` beside this file. Content: provenance writes
for the `~/.agents` skill surface and the Antigravity plugin skill surfaces in
both injectors, plus a fail-closed `resolve_authority` branch for an installed
projection carrying `MANIFEST.json` but no installer provenance marker.

MTimes (UTC): inject.ps1 18:04:00, inject.sh 18:04:08, runtime_bootstrap.py
18:04:13 -- three sequential writes inside 13 seconds.

## 2. Detective -- who wrote it

Writer: the Antigravity agent **buffy**, conversation
`c4c8380f-1d7a-4926-84ce-88f9ccc7770e` (a child trajectory of
`0ad017b8-903d-4299-acbb-1830885fab2f`), working the AUDAPACK objective
"P0 + P1 Escaped Regression Closure".

Tool-level evidence in that conversation, quoting its own tool calls:

- `replace_file_content` -- "Write runtime provenance for freebuff and
  antigravity skills", target `.../_SAIPEN/bootstrap/inject.ps1` (StartLine 534);
- `replace_file_content` -- "Write provenance for ~/.agents in inject.sh",
  target `.../_SAIPEN/bootstrap/inject.sh` (StartLine 556);
- `replace_file_content` -- "Detect installed projection missing provenance in
  resolve_authority", target
  `.../_SAIPEN/tools/saipen_engine/runtime_bootstrap.py` (EndLine 475);
- its own completion report: "Files Modified & Verified for P0 ...
  bootstrap/inject.ps1 ... bootstrap/inject.sh ... runtime_bootstrap.py ... Ran
  inject.ps1: Generated verified .saipen_runtime.json in
  C:/Users/vac34/.agents/skills/saipen".

Corroborating timeline:

    18:03:36  tools/__pycache__/test_runtime_bootstrap.cpython-311.pyc rewritten
              (a runtime-bootstrap test import immediately before the edits)
    18:04:00  inject.ps1 written
    18:04:08  inject.sh written
    18:04:13  runtime_bootstrap.py written
    18:04:19  ~/.gemini/skills/saipen/.saipen_runtime.json (inject run)
    18:04:20  ~/.agents/skills/saipen/.saipen_runtime.json (new provenance path)
    18:04:19-22  Antigravity plugin skill targets refreshed with the new bytes
    18:24     its report says AUDAPACK ticket T-195 finished
    18:26:46  conversation last updated; no SAIPEN activity after that

No OpenCode session existed between 16:24Z and 19:00Z, so the delta is not
OpenCode-hosted. The Claude Code SAIPEN project store was checked for the
distinct strings; its sessions that carry this text predate the delta (09-14 /
09-15) and their transcripts were not written on 09-17 18:04Z. Two other
foreign touches were found and are recorded in section 5.

## 3. Prosecutor -- is it legitimate?

- A valid active ticket existed, but in ANOTHER project: AUDAPACK `T-195`
  ("P0: managed OpenCode launch blocked by SAIPEN source architecture proof"),
  finished 18:24 by the same agent. SAIPEN's BOARD carries no ticket for this
  change and its LOG has no event at 18:04Z.
- No SAIPEN seat: SAIPEN `STATE.agent` is `claude`; the writer is `buffy`,
  a foreign project's agent. No SAIPEN claim was made.
- Scope: the writer patched SAIPEN-owned product bytes to unblock its own
  project's launch, then verified in its own context (its report: launcher
  tests green, live launches). That is a real motive and a coherent fix, but
  it is a foreign project editing this repository's source without this
  repository's ownership.
- Journaling: journaled in AUDAPACK's ledger only; nothing here.
- Timing: the writes (18:04Z) postdate T-1385's VERIFY proof (E-7006,
  16:29:50Z), so the old VERIFY evidence describes T-1385's own bytes, not
  the current worktree.
- Hostile intent: none evidenced. The agent reported the files it changed and
  the verification it ran; it did not hide the change.

## 4. Judge -- classification

**LEGIT_FOREIGN_ABANDONED** (useful).

Its own ticket is terminal, the writer is inactive, the content is coherent and
was verified only in the foreign context, and no bypass intent is evidenced.
The bytes are nevertheless foreign to this repository's authority chain until
this repository owns and proves them.

## 5. Other foreign touches (recorded, no byte effect)

- OpenCode session `ses_f4f361301ffel3jqnuCHBJ9UiH` (AUDAPACK, "AUDAPACK
  markdown file review") made two `edit` calls on
  `tools/saipen_engine/admission.py` at 19:26:15Z and 19:26:22Z that exactly
  revert each other (1131 -> 2284 -> 1131 bytes, same text). Net content
  effect: none; mtime only. Read-only in effect, no ticket required; recorded
  so the mtime is not mistaken for missing content.
- A PCN refusal reproduced in THIS session at ~19:37Z while a read command
  named `.saipen`: the host error carried `attempted:` and
  `next: saipen next --json`. That is T-1385 evidence, filed with T-1385.

## 6. Disposition applied

- Bytes preserved exactly (hashes above, diff in this directory).
- Not attributed to T-1385; excluded from T-1385's commit.
- A dedicated SAIPEN adoption ticket is allocated (see LOG for its id) to
  prove and commit the delta under this repository's own gates.
- The T-1384 corrective ticket is allocated separately (see LOG), and T-1385
  is parked on it through `ticket block-for`.
- No inject, no push, no tag: injection resumes only after the corrective
  commit exists and this delta has an owner.
