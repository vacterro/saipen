# T-1623 — protocol budget effects

T-1623 touched two independent protocol gates. They were resolved differently
and the difference is recorded here on purpose.

## 1. `command_resolution` — re-derived, 52 KiB -> 53 KiB

`tools/test_protocol_registry.py::test_every_declared_load_budget_is_measured_from_registry`
measured `command_resolution` at **53592** bytes against a declared **53248**
(52 KiB), so `saipen/REGISTRY.json`'s declared budget moved to the next whole
KiB, **54272** (53 KiB).

What consumed the 344 bytes of slack:

- `protocol_admission.host_authority`: the broker's configuration surface --
  broker/client/service-entry owners, transport, capability TTL, idle exit,
  ancestry limit, the four accepted host image names, the degraded-mode policy
  and the recorded known limit;
- `protocol_admission.states`: `DEGRADED`, the operator-explicit fallback state
  now part of the owner's vocabulary;
- `error_codes`: the broker's refusal codes.

No rule, document, command or declaration was dropped to pay for it, and no
other profile moved.

## 2. `human_markdown_total` (324 KiB, hardcoded) — paid for by trimming, NOT re-derived

The first wording of the new `saipen/EXECUTION.md` paragraph (+340 bytes) pushed
the total protocol markdown surface to 331961 against the hardcoded 331776 cap,
so the paragraph was tightened to its current +147 bytes and the gate passes
without touching the cap.

The measured surface is close to that cap because a *pending, unrelated* change
in this working tree (`saipen/RUNTIME.md`, +2222 bytes, not this ticket) has
already spent most of the remaining room. That is recorded rather than silently
absorbed: the next change that grows the human markdown surface will have to
re-derive this cap with its own evidence file, the way T-1595 did
(300 KiB -> 301 KiB).

## Re-measurement

    python -m unittest tools.test_protocol_registry

16 tests, OK. `human_markdown_total` passes with the trimmed paragraph; every
declared load profile measures under its declared budget.
