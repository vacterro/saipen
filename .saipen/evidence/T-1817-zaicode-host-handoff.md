# T-1817 / SRC-276 R006 — ZAICODE-owned handoff (F-06, F-08, F-09, F-10, F-12)

Date: 2026-10-22. SAIPEN-side work for these findings is bounded and delivered
where SAIPEN owns the surface. The findings below name ZAICODE as the
corrective owner; this document is the handoff, not a claim that the host work
is done. No ZAICODE source was edited from this checkout, and the original
observed project `_SMART_VAC_MEDIA_COMPRESSOR` was not mutated.

## Why this split exists

The observed session ran on ZAICODE 0.0.3. Five of its findings live on the
host's answer/observation surface and UI task list. SAIPEN can prove its own
side of each contract; it cannot change how the host renders, enforces or
reports. Claiming these DONE from here would be false green, so they are handed
over with the exact evidence each closure needs.

The findings in this document are all class `UNAVAILABLE_EXTERNAL` for the
purposes of `saipen_engine/finding_ownership.py`, except that the host is the
owner rather than an unavailable third party. Everything class
`ENGINE_INTERNAL` (F-01, F-02, F-03, F-05, F-07, F-11) and the one
`OPERATOR_DECISION` (F-04) is delivered or tracked in
`.saipen/evidence/T-1817-diagnosis-delivery.md` and must never appear here as a
host obligation — that misclassification is exactly F-11.

## F-08 — chat language / structure / HUSH drift; host enforcement unavailable

**What the record proves.** At ingress the host recorded `styleHash:
sha256:a3fbbfe52cfc` and `executionHash: sha256:23af34e64605` with
`enforcement.language: none`, `enforcement.structure: none`
(`.saipen/intake/active/SRC-276.md`, [L392–409]). STYLE pins
`reply_language: et`; EXECUTION requires the typed control-first final and
HUSH. The visible output drifted to English multi-paragraph narrative
([L18410–18442]).

**What SAIPEN already owns and can prove.** `saipen response style --json`
compiles STYLE+EXECUTION into one contract (`reply_language: et`, budgets,
banned openers/closers, `source_token`). `saipen response digest
--reason final|stop|status --json` is the machine control surface;
`saipen response render --stdin` is the diagnostic renderer. `tools/saipen.py`
also answers `response check --stdin`. These exist; they do not run themselves
at the host reply surface.

**What ZAICODE must do.**
1. Bind the admitted `styleHash`/`executionHash` to the actual answer
   renderer, and invalidate the binding when either document changes (a stale
   admitted hash must not authorize a current reply).
2. Compile the pinned reply language mechanically; `replyLanguage: null` in
   the admission record must resolve to STYLE's `et`, never to the user's
   language.
3. Run the typed-final check against the rendered text before it becomes
   visible, and report `ADVISORY` vs `MECHANICAL` honestly — the registry
   already declares `zaicode` as `ADVISORY` / `ADVISORY` / `response_hook:
   null`, which is the truthful current capability. Do not upgrade that claim
   without a `response_hook` token the hook artifact actually contains.
4. Preserve genuine higher-priority safety overrides; a safety notice is not
   HUSH drift.

**Acceptance from the ZAICODE side.** A regression that ingresses a
non-Estonian user message under `reply_language: et` and asserts the visible
reply is Estonian and structurally typed; a second that changes STYLE and
asserts the stale admitted hash no longer authorizes a reply.

## F-09 — partial-observation pattern (`| head`, `| tail`)

**What the record proves.** Decision-bearing reads were truncated:
`saipen cc --json | head -100`, `saipen validate --json | head -60`,
`saipen status --json | head -40`, `cat .saipen/BOARD.md | head -60`
([L694–739], [L7550–7600], [L12850–12955], [L13930–14035]). No missed
actionable Work is proven; the pattern is the defect.

**What ZAICODE must do.** Read decision-bearing output to EOF or parse the
JSON; preserve the producer exit code (a pipe masks it). Exploratory
`grep`/`head` is not decision-grade evidence, and truncation never proves
"no actionable work".

**Acceptance.** A fixture whose actionable record sits below line 60 of the
owner-selected current work; the host must still surface it.

## F-10 — negative evidence overstated as historical non-existence

**What the record proves.** The final said the archive sidecars "never
existed / were simply never written" on the strength of a Git query that
reported no tracked history and `?? .saipen/archive/source/`
([L10660–10765], [L18410–18442]).

**What ZAICODE must do.** Distinguish three claims mechanically: *not present
in the current tree*, *not available in the checked Git history*, and
*historical origin unknown*. The third is the only honest one here.

**Acceptance.** A closed-world/negative-evidence wording test: an
untracked-path observation must not render as "never existed".

## F-06 — unsupported exhaustive-check claims

**What the record proves.** "I ran every engine-authority route against it,
all refused" ([L18410–18442]) while the captured runs include
`saipen source recover` → `ok:true, orphans: []` and
`intake.close_receipt` → `ok:true, SOURCE_CLOSED`, plus refusals, and
`source retire` / `source quarantine` were only code-read
([L9540–9610], [L14896–14980]).

**What ZAICODE must do.** Keep an execution ledger with three states —
executed / read-only reviewed / not attempted — and three outcome classes —
`SUCCESS_NO_CHANGE` / `REFUSED` / `REPAIRED`. Prohibit "all tested" wording
that is not backed by coverage of the full known command set.

**Acceptance.** A recap oracle that fails when a summary claims exhaustive
execution while the ledger contains a code-read-only or not-attempted entry.

## F-12 — host TODO list vs Work/goal completion

**What the record proves.** Every host TODO was marked completed (including
`T-62 blocked … awaiting human authority`) while BOARD had T-62 BLOCKED and
the goal verifier returned `passed:false` ([L18274–18332], [L18520–18575]).
No false goal PASS occurred.

**What ZAICODE must do.** Label local diagnostic TODOs separately from SAIPEN
Work and goal completion, and make local checklist completion mechanically
incapable of implying ticket or goal DONE.

**Acceptance.** A fixture with an open BLOCKED ticket and a fully-checked
local TODO list; the goal surface must still read not-complete.

## What this handoff does not claim

- It does not claim any ZAICODE edit exists.
- It does not claim the historical origin of the missing SRC-003 sidecars.
- It does not claim the host's enforcement outside the captured session is
  known; the capture documents `enforcement: none` for that session only.
- It does not reopen FUTURE_GATE, and it grants no goal pivot.
- A host finding whose classifier family is not recognized stays `UNKNOWN`
  here rather than being assigned a class; `UNKNOWN` is an honest label, not a
  fourth owner, and it must never render as an operator obligation.
