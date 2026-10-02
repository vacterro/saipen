# T-1583 — Response-enforcement escape, 2026-10-01 11:28:57Z (forensic, no patch)

Incident: one real assistant reply (Estonian, 7 non-empty prose lines, 2631
prose chars) answered an ordinary Russian question with no DETAIL
authorization and reached the operator unmeasured. This report is the single
proven causal chain. No code, STYLE or registry bytes were changed.

## 1. The live host (machine-proven, not UI-inferred)

- Producing host: **production ZCode CLI** (the very host class running this
  investigation is not the incident host; the incident host is identified
  below from its own transcript store).
- Transcript: `C:/Users/vac34/.zcode/cli/rollout/model-io-sess_d9be29f2-cde3-419e-84c2-851fa47ff1e4.jsonl`
  (10.3 MB, sha256 `b24a34ec9ee184fb829f84ea5356612bf79345f6fe99d6a1a2739e60cf309ad6`),
  43 model-io records 10:55:34Z–11:28:57Z, `querySource: main_turn`.
- Session `sess_d9be29f2-cde3-419e-84c2-851fa47ff1e4`, workspace
  `V:\___VAC\__K\__CODE\_PY\_FastPrompter`, model `SAIFREN@new-provider`.
- Incident turn `turn_ebdb9065`, completedAt `2026-10-01T11:28:57.559Z`:
  ingress at `request.messages[63]`, reply at `response.text`,
  `response.reasoningText` 12213 chars.
- Carrier bytes (re-extracted binary-exact from the rollout record):
  - `ingress.txt` — 190 chars / 342 bytes UTF-8, sha256 `fd7bed0eef4f1bb2338817eaba94ceadb5dd2e37d869470c74d1b720404b73d2`.
  - `reply.txt` — 2643 chars / 2716 bytes UTF-8, sha256 `d6c2c592a71631666a19ad1d0fc89ff90300572025ae2b74f1fc7e27c7c6c9f0`
    (an earlier copy was CRLF-translated to 2655 chars; discarded).
- Incident project's bound SAIPEN home:
  `V:/___VAC/__K/__CODE/_PY/_FastPrompter/.saipen/STATE.md:8` →
  `C:/Users/vac34/.agents/skills/saipen` (an installed home, not this repo).

## 2. Authorization replay (fork resolved: authorization was never granted)

`saipen_engine.response_surface.detail_mode_for_request(exact ingress)` →
`NONE`. The grammar is English-only (write/prepare/produce/give/send/render +
report/write-up/summary/brief; audit; handoff; exceptional-boundary clause).
The Russian ingress matches nothing. **DETAILS was machine-forbidden.**

## 3. Classifier replay (fork A: the classifier is correct in the repo)

- Current repo bytes (T-1558 working tree):
  `classify_final_response(REPLY, operational_turn=False, style_contract=compiled, detail_mode=NONE)`
  → `CHAT_STYLE_DRIFT`, layer CHAT_STYLE, error
  *"chat prose is 2631 characters; the ceiling is 2000"*.
- The incident project's **installed** home (`C:/Users/vac34/.agents/skills/saipen`)
  classifies the SAME bytes `ORDINARY_CHAT` / ok:true — `CLASS_CHAT_STYLE_DRIFT`
  does not exist there.
- Installed-home matrix (refs of `CLASS_CHAT_STYLE_DRIFT` in each home's
  `response_surface.py`): `.agents` 0, `.codex` 0, `.claude` 0, opencode 6,
  ZAICODE isolated dev home none (ships no engine), `.gemini` 0,
  `scheduled-source` 0. The scheduled runtime additionally refuses the
  command outright (`RUNTIME_DRIFT`: "command 'response' is not implemented
  by this runtime").
- Distribution freeze: 6/6 installed homes stale (newest installed head
  `5766cd54` < source `655fadff`); the scheduled injector is blocked
  `DIRTY_SOURCE` (205 injected-surface paths differ from HEAD; the T-1558
  guard bytes are uncommitted working-tree edits). So even a fresh inject
  cannot ship the fix until it lands.

## 4. Generative cause (from the model's own reasoning, verbatim)

> "Style: caveman-дед, Estonian, ≤5 lines normally but this is a technical
> multi-item explanation — max 8 lines guidance. But the content genuinely
> needs enumeration. The style file says \"Reports ≤5 lines (absolute max 8
> lines)\". But my system prompt also says security warnings / multi-step
> sequences → plain prose, and readability matters. The user explicitly asked
> for \"точную..."

The model knew the line budget (7 ≤ 8 lines — complied) and then **invented**
length/detail authorization from content-need plus the caveman tone rule's
auto-clarity clause plus "user asked for точную причину". No canonical
authority grants that: detail authorization is a machine fact derived from
the human's request (`response_surface.py:71-77`). "User may request
content" ≠ "user mechanically authorized DETAIL mode" — confirmed by §2.

Contributing delivery gap (measured on the pre-incident turn context): the
2000-char ceiling and the machine-owned DETAILS machinery appear in NO
surface the session actually loaded. Installed and source `STYLE.md` carry
only the line budget ("Reports ≤5 lines (absolute max 8 lines)"); the ceiling
exists in `response_surface.py` and one line of `EXECUTION.md:42` (filename
present in context, the budget line not quoted into it); the generated chat
contract that does carry the 2000-char line is delivered by host hooks this
host does not have. The model was never shown the rule it broke.

## 5. Host enforcement path (edge-by-edge: zero boundaries)

Registry truth (`extensions/adapters/registry.json`):
- `zaicode` entry covers ONLY the isolated dev home
  (`$ZAICODE_HOME = V:\..._ZAICODE\.zaicode\home`), response_enforcement
  **ADVISORY**, `hook_install_surface: null`, and states it never shares
  `~/.zcode` with a production ZCode. **The production ZCode CLI is
  UNREGISTERED** — no entry, no hook surface, no transport.
- codex/claude: MECHANICAL via Stop hook on `last_assistant_message` —
  post-render detection, one correction continuation, not pre-display
  blocking. opencode: COMPLETED_TEXT_PART (pre-output).
- silent_tool_continuation / intermediate_text_suppression: ADVISORY
  (instruction-only) on ALL hosts — no host can mechanically enforce them.

Guards actually on this machine: `~/.codex/hooks/saipen-guard.py` (4
response-check refs), `~/.config/opencode/plugins/saipen-guard.js` (2 refs),
`~/.claude/hooks` has NO saipen guard. None of these hosts was the incident
host. For the incident turn the enforcement path is: **no admission
transport → no chat-contract injection → no pre-output interception → no
post-output Stop gate → text rendered unmeasured.** The operator saw the
full reply before any enforcement could exist; this was not "late
correction", there was none. Language selection (Estonian) is a separate,
correctly-enforced property (`reply_language: et`) and did not participate:
a compact Estonian reply on the same ingress classifies `ORDINARY_CHAT`.

## 6. Verdict (acceptance item 9): COMBINATION

1. **Implementation-behavior defect (model invention)** — §4.
2. **Contract-delivery gap** — the measurable ceiling is hook-delivered;
   hookless hosts never see it (§4).
3. **Stale installation** — T-1558's classifier is correct but unshipped
   (DIRTY_SOURCE freeze; 6/6 homes lack it) (§3).
4. **Host capability limit** — production ZCode has no registered gate
   surface at all (§5); on this host class SAIPEN can at best DETECT
   post-display, never prevent. Hard prevention must not be claimed.

## 7. Protocol owner (existing Work, no duplicate created)

- **T-1558** (P1, "агент пишет романы вместо протокольного ответа") — parent
  owner of the chat-style enforcement class; BLOCKED chain
  T-1563 → T-1562 → T-1558, resume BUILD. Landing it + clearing DIRTY_SOURCE
  is what makes installed classifiers refuse this class.
- Related, not owners of this incident: T-1551 (codex Stop-hook trust proof),
  T-1568 (OpenCode chat-style enforcement), T-1559 (STYLE two-owner drift —
  coordinate any STYLE.md line addition with it).
- **Gap found**: NO existing ticket owns registering the production ZCode CLI
  in the adapter registry. Recommend one smallest Work item (registry entry +
  a hookless-visible contract surface), decision left to the protocolist.

## 8. Required repair (proposed only — nothing patched)

1. Land T-1558 bytes, clear DIRTY_SOURCE, inject: installed homes then refuse
   the exact incident class (`incident.py` stays green as the proof).
2. Deliver the measurable chat contract (2000-char ceiling + machine-owned
   detail authorization) through a surface hookless hosts DO load (STYLE.md
   line / activation block; coordinate with T-1559's two-owner work).
3. Register production ZCode honestly: response_enforcement ADVISORY,
   `hook_install_surface: null`, so `status` reports the true boundary
   instead of silence.

## 9. RED control

`incident.py` — same-incident regression (exact ingress + exact reply, both
digest-bound): detail_mode NONE on the exact ingress; line budget alone
cannot catch it (7 ≤ 8); canonical classifier refuses (`2631 > 2000`);
compact reply on the same ingress stays ORDINARY_CHAT. Run:
`python .saipen/evidence/T-1583-response-escape-20261001/incident.py [subject-root]`
→ 5/5 OK at capture time. Goes red if any future change re-accepts these
exact bytes. (A "hello"→9-line toy is NOT the carrier; the real incident is.)
