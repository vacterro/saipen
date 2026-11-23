# Stable verification environment — T-1834

The live T-1833 generation `6a087f6f912fac56` was verified twice in separate
tool calls (72.032 s and 114.968 s). The second command generated another
record instead of reusing the first. Both recorded the same source; their
only changed compatibility component was `environment_sha256`. A per-key
hash comparison across actual host calls identified only `CODEX_TOOL_CALL_ID`.
Raw environment values were neither needed nor stored for that comparison.

The same difference caused a real canonical refusal:
`INCOMPLETE_TICKET -- focused check has missing or incompatible verification
environment identity` when the reviewed T-1833 tried to enter SHIP. This is
recorded as a dependency of T-1833, not as an accepted exception to the gate.

The Windows launcher subsequently exposed a second diagnostic difference:
`cmd` adds `PROMPT`. The actual launcher script also runs the managed Python
runtime, whereas the initial evidence used the ambient user Python. That
interpreter mismatch was correctly refused and is retained as a safety control;
the existing evidence command is now executed with the observed managed runtime.
Hash-only direct/launcher comparison proved PROMPT was the sole remaining
environment difference. After normalization their child environments match.

The correction removes CODEX_TOOL_CALL_ID and PROMPT from the existing actual
canonical child environment before its execution and before compatibility
capture. It does not merely suppress a field while leaving two different
executed environments. Every other environment input, including the explicit
`SAIPEN_TEST_MODE` negative control, remains part of identity.

The identical final two-test oracle fails on the prefix runner and passes on
Windows and Linux after the change. A real spawned child observes no tool-call
carriers; cached records remain compatible across different diagnostic values;
changing the semantic mode invalidates them. `prefix-final-oracle.log`,
`postfix-final-oracle.log` and `postfix-linux.log` preserve those results. The prefix runner
is saved locally for rollback. Scoped lint passes.

Canonical combined focused execution, reuse across separate host calls and
the previously refused SHIP transition are verified by the subsequent current
LOG events and focused execution receipts. No full-family, total campaign
speedup, release or publication claim follows from this bounded correction.
