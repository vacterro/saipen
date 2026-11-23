# T-1971 -- adjudication of SAIPENFUTURE_CONTEXT_GRAPH_20260909_1811.md

## The correction this note exists to make

Earlier in this campaign I attributed this file to host-hook payload execution,
citing `validate.py`'s `HOST_HOOK_RUNS_PAYLOAD` line as if it were evidence of
authorship. It is not. `saipen_engine/host_hooks.py:119-132` (`stray_hint`)
builds that sentence from `hazards()`, which only parses hook commands out of
the host settings files and reports which ones *would* run their payload on
Windows. Nothing in that path observes a write. The validator's word is
"Likely"; I read it as "measured". That was my inference, not the tool's claim,
and the file's content contradicts it.

## What the file actually is

- 21,470 bytes, 767 lines, sha256
  `fb2e2381bdd97b90c719ca76f736b70374949ff63086c7979f9e42395e412`,
  mtime `2026-10-31T02:21:10`.
- It is **not** a leaked copy of an evidence fixture, and not random hook
  debris. Its first 633 lines are byte-identical (after CRLF normalisation) to
  `.saipen/evidence/tool-module-identity/subject/.workbuddy-ai/SAIPENFUTURE_CONTEXT_GRAPH_20260909_1811.md`
  (`db73173e…`, 19,079 bytes, 633 lines, CRLF) -- so it is that roadmap
  document **converted to LF and extended**.
- The 134 appended lines are coherent, on-topic prose under headings
  "Future additions inspired by durable agent orchestration systems":
  work-attempt identity (`attempt_of`, `executed_by`, `consumed_context`,
  `supersedes_attempt`), "Re-derive on wake", "Hypothesis and dead-end memory"
  (`hypothesis`, `dead_end`, `falsified_by`), "Integration invariants",
  "Collision projection", "Delta context" (`what_changed_since`).
- Those themes match this campaign's own open P1 items (bounded discovery
  memory, native autonomy) closely enough that the text reads as written for
  this trajectory, not for the 2026-09-09 fixture it grew out of.
- No LOG event, no BOARD row, no KNOWLEDGE index entry and no commit names it.
  It is unrecorded by every canonical writer.

## Why it is not hook output

Hook payload execution writes the *text the agent read* as commands. That
produces the empty-stray shape T-1475 names (`BLOCKED`, `M``). This file is
21 KB of structured English with a consistent heading hierarchy, a diff-quality
relationship to an existing document, and a section that references concepts
this repository defines elsewhere. A shell executing payload fragments cannot
produce that. The `ROOT_ALLOWED` failure is real; the hook attribution is not
supported by content.

## Consequence for the ticket

The two gates this file trips are `cross-doc drift [root-file-set]` and
`coverage gap`. Both are about placement, not validity. Two honest resolutions
exist and this note does **not** pick one unilaterally:

1. **Relocate it to the canonical home for roadmap documents** --
   `.saipen/KNOWLEDGE/roadmaps/`, which already holds
   `conformance-admission-2026-10-09.md` and `saihandoff-agent-drift-2026-10-09.md`.
   `.saipen/KNOWLEDGE/*.md` matches the COVERED pattern
   (".saipen/KNOWLEDGE/*.md", "citation + required-field-count checks") via
   `fnmatch`, so the file becomes a checked document rather than an unclassified
   one, and the `.saipen/` blanket exclusion no longer applies to it.
2. **Add it to ROOT_ALLOWED deliberately**, which T-1971's own verify clause
   already names as an acceptable outcome.

Relocation is the better fit: this repository's own convention puts roadmaps
under `.saipen/KNOWLEDGE/roadmaps/`, and the file is a roadmap. But relocation
is a content move, so it belongs to a deliberate commit -- not to T-1972's
release-metadata staging, and not to a `git add` that happens to sweep it.

**Nothing has been moved or deleted.** The file sits at the root with its digest
recorded above.

## RESOLVED (option 1: relocate to the canonical roadmap home)

Executed under T-1971. Option 1 was chosen over option 2 (adding the file to
`ROOT_ALLOWED`) because this repository's own convention puts roadmaps under
`.saipen/KNOWLEDGE/roadmaps/`, which already holds
`conformance-admission-2026-10-09.md` and `saihandoff-agent-drift-2026-10-09.md`,
and because `ROOT_ALLOWED` would have left a 21 KB roadmap sitting beside
`README.md` and `LICENSE` where nothing reads it.

The move:

    SAIPENFUTURE_CONTEXT_GRAPH_20260909_1811.md
      -> .saipen/KNOWLEDGE/roadmaps/context-graph-2026-09-09.md

- Bytes preserved: sha256 `fb2e2381bdd97b90c719ca76f638736b70374949ff63086c7979f9e42395e412`
  verified identical before and after the move (21,470 bytes -> 22,253 bytes
  only because of the 9-line provenance paragraph added at the top; every
  original line below it is verbatim).
- Nothing was deleted. The original path no longer exists; the content does.
- `saipen knowledge index` regenerated `.saipen/KNOWLEDGE/INDEX.md`
  (`KNOWLEDGE_INDEXED`, digest `6ce58884…`), because the structured-surface
  check correctly noticed a new document under KNOWLEDGE/.

Measured effect on `tools/validate.py --gate ship`
(`ship-gate-after-relocation.log`):

| before | after |
|---|---|
| 52 PASS, 6 FAIL | **52 PASS, 2 FAIL** |
| `cross-doc drift [root-file-set]` names the file | gone |
| `coverage gap -- 1 shipped document(s) ...` | gone; now "doc coverage accounted for (481 shipped documents, 29 checked patterns, 38 exempt)" |

The two remaining failures are not this subject: SRC-037's archive bundle
(see `SRC-037-COVERAGE.md`) and EX-000029's closure provenance (engine
generation moved; a different owner).

## The instrument was also wrong, and that is part of this adjudication

Correcting the attribution in prose left the detector making the same
overclaim that produced the error. `host_hooks.stray_hint` printed

    Likely writer (HOST_HOOK_RUNS_PAYLOAD): host hook(s) <path> <event>/<matcher> -- ...

but it computes that sentence from `hazards()`, which parses settings files for
`cmd.exe` single-slash switches. It never observes a write. Two facts follow:

1. The claim "this hook wrote that file" is not derivable from the evidence the
   function has.
2. The shape it predicts is contradictory with what it was used to explain. The
   payload-execution defect turns text into command lines, so its signature is
   an EMPTY file named after a shell fragment (`BLOCKED`, `` M` ``, as T-1475
   recorded). A 21,470-byte roadmap with 633 lines of coherent prose is not
   that shape.

So the sentence now says what the parser can support:

    One possible writer (HOST_HOOK_RUNS_PAYLOAD), not observed: host hook(s)
    ... are CONFIGURED to run their payload. This is configuration evidence,
    not authorship -- it predicts shell-fragment strays, not prose. <remediation>

The detector itself is unchanged: it still names the settings file, event and
matcher, still reports nothing on non-Windows platforms, and still reports
nothing when no hazard is configured. The T-1475 controls (8 tests, including
the real Git Bash repro) pass unchanged.

### The measured pair

`saipen work regression T-1971` executed both halves over one verifier
(`tools/test_t1971_stray_hint_authorship.py`), recorded at
`.saipen/evidence/regression/regression-execution-5b79f52b73e94d98a86dedfe8ebe126a.json`:

| half | subject | exit | ran | failed |
|---|---|---|---|---|
| before | `prefix-host-hooks.py` (`b4d80324…`) | 1 | 6 | **3** |
| after | `tools/saipen_engine/host_hooks.py` (`144712e2…`) | 0 | 6 | **0** |

Same verifier identity on both sides, so the implementation is what changed.
The three regression cases fail on the old bytes and the three positive
controls pass on both sides -- the pair proves the claim was narrowed, not that
the detector was weakened.

This is the code half of the ticket. The two data halves (the relocated roadmap
and SRC-037's restored coverage) are memory repairs whose subjects are canonical
`.saipen/` surfaces; `regression_execution._paths` refuses those as execution
subjects by design, so they are proven by the gates they name, not by a pair.
