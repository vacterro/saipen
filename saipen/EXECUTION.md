# SAIPEN Execution Policy

This document owns output and narration policy. It does not own lifecycle,
command routing, safety authorization, or chat voice.

<!-- RULE-OWNER: EXEC-HUSH-01 -->

## Precedence

`user/safety/CORE > execution policy > STYLE`

A higher layer always wins. HUSH cannot suppress a safety refusal, a required
human decision, an error needed to act, or the final evidence report. STYLE
selects language and voice only after this policy decides whether text exists.

## Default execution

- Emit a short commentary update before tools and at meaningful boundaries.
- Prefer action and evidence over narrating each tool call.
- Report failures when they occur; continue autonomously when the repair is
  authorized and deterministic.
- Finish with the outcome, verification, remaining blocker, and material file
  changes. Do not dump a tool transcript.

## HUSH

`hush <task>` applies to that task and its authorized continuation chain.

- Tool-first: begin work without conversational preamble.
- Silence lock: omit progress narration, plans, and success chatter.
- Structured command results and machine-readable evidence are data, not
  narration; retain them when a caller requires them.
- Mandatory output exceptions: safety/destructive confirmation, missing human
  authority, terminal failure, protocol corruption, externally visible side
  effects requiring acknowledgment, and the final evidence report.
- The final report is at most 20 lines and contains only outcome, verification,
  changed scope, and unresolved facts.

Audits remain lossless: HUSH suppresses chat noise, never source capture,
coverage, LOG evidence, findings, test output required by a gate, or failure
diagnostics. HUSH ends when its task reaches a terminal result or the user
explicitly cancels it.
