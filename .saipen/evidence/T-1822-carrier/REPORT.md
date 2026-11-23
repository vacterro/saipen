# T-1822 — carrier binding: an operator carrier belongs to its delivering session

Source: SRC-280. Verify: *Freebuff live GUI: genuine operator cc resumes paused
bounded goal with host carrier; model-authored/tool-generated/replayed/wrong-session
carriers refused; SAFE failure HOST_PROVENANCE_UNAVAILABLE.*

## Scope split: what this repository can and cannot prove

SRC-280 asks for two different things, and only one of them lives here.

**Host-side (NOT satisfied here, and not satisfiable here).** The transport that
would give a real FreeBuff `cc` trusted provenance is a FreeBuff obligation: the
launcher exports `SAIPEN_TASK_FILE`/`SAIPEN_TASK_SHA256` for the tool process it
spawns, or the host writes a `.saipen/cache/ingress/` envelope on operator input.
T-1822 measured live that a genuine operator `cc` typed in the FreeBuff UI reaches
the engine with none of those, which is why the witness is `model_supplied` and
`operator_required` correctly refuses it. `extensions/adapters/registry.json`
records that as `host_prompt_available: false`, `prompt_to_work_binding:
NOT_INSTALLED`, `supported_carrier_mechanisms: []`. SAIPEN must not manufacture a
host carrier for itself.

**Engine-side (fixed here).** What the engine does with a carrier *once one
arrives*. Two defects were measured by execution before any change:

1. `operator_task.witness()` called `active_host_ingress(root)` with no session
   filter. An envelope stamped `session_id=session-A` was consumed when session B
   supplied the same text, and `authority_for_provenance()` returned
   `user_explicit: True`. A replayed, wrong-session carrier earned the operator's
   authority — the exact opposite of the refusal SRC-280's verify demands.

2. `admit_host_ingress()` named envelopes `ing-<digest16>`, a function of the
   request *text* alone. Two sessions delivering the same words shared one path,
   and the later write replaced the earlier envelope including its `session_id`
   and `message_id` (measured: `m-A` replaced by `m-B`). The operator's own record
   was destroyed silently.

## Change

`tools/saipen_engine/operator_task.py`

| Before | After |
|---|---|
| `witness()` matched any active envelope by digest, ignoring `session_id` | matches only an envelope whose `session_id` is the delivering session (`SAIPEN_HOST_SESSION`), or one that names no session (legacy shape) |
| a wrong-session match was consumed and reported `operator_carrier` | returns `HOST_PROVENANCE_UNAVAILABLE` with `carrier_session`, `delivering_session`, `supplied_digest`; the envelope is left unconsumed |
| envelope id `ing-<digest16>` from request text | `ing-<digest(message_id + text)[:16]>`; a genuinely different delivery that collides is disambiguated, never overwritten |
| a repeat delivery silently returned the old id | same message + same session + same digest is idempotent and writes nothing |

New: `ENV_HOST_SESSION`, `host_session()`, `CODE_HOST_PROVENANCE_UNAVAILABLE`.

`tools/test_operator_ingress_matrix.py`: two fixtures simulated a host delivery
but never exported the session the adapter always sets per event
(`extensions/adapters/opencode/saipen-guard.js`, T-1384). The simulation was
corrected, not the rule.

## Evidence

- `tools/test_t1822_carrier_binding.py` — 8 tests, all green:
  - `test_wrong_session_envelope_is_refused_not_promoted`
  - `test_refused_replay_leaves_the_owner_envelope_unconsumed`
  - `test_delivering_session_still_earns_operator_authority`
  - `test_same_text_from_two_sessions_keeps_both_envelopes`
  - `test_redelivery_of_one_message_is_idempotent`
  - `test_unnamed_legacy_envelope_stays_admissible`
  - `test_no_carrier_at_all_still_reports_model_supplied`
  - `test_safe_failure_code_is_the_one_src_280_names`
- Red control (`red-control.txt`): both original defects restored in a disposable
  copy → 3 failures, exit 1. Each failure names a real defect signature.
- Combined suites: `tools.test_freebuff_operator_provenance`,
  `tools.test_operator_ingress_matrix`, `tools.test_t1822_carrier_binding` →
  Ran 46, OK (skipped=1: the live-host acceptance, which correctly skips).
- Related engine suites: `test_operator_task_witness`, `test_ingress_authority`,
  `test_protocol_admission`, `test_entry_answer_agrees`,
  `test_t1461_source_append` → Ran 155, OK (skipped=3).

## What remains a genuine external dependency

`tools/test_freebuff_operator_provenance.FreebuffLiveHostAcceptance` still SKIPS
without `SAIPEN_FREEBUFF_LIVE_CARRIER`/`SAIPEN_FREEBUFF_LIVE_SHA256`. The live GUI
acceptance in SRC-280's verify — a real operator turn in the FreeBuff UI resuming
a paused bounded goal — cannot be produced by this repository. It needs a
FreeBuff host that exports the carrier, i.e. the FreeBuff-side change described
above, followed by an operator run in an authorized disposable project.
