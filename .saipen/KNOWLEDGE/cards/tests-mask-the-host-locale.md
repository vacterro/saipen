<!-- SAIPEN KNOWLEDGE CARD v1 -->
kind: trap
scope: subprocess, stdin, text mode, encoding, Windows, tests, hooks, validator
trigger: passing text to or reading text from a child process, or writing a test that spawns one
status: active
evidence: T-1558, tools/test_validator_layout_parity.py, tools/test_chat_style.py, tools/test_claude_stop_hook.py
supersedes: none

# Give every child-process text an explicit encoding

Pass bytes or `encoding="utf-8"` (and `errors`) to every subprocess, and give the test that covers it a narrow-locale environment, because text mode uses the host locale and the tests' own `PYTHONUTF8=1` hides the failure.

Why:
On a cp1251 Windows host text mode has no Estonian letters and no box glyphs: a validator crash on a hook-written root stray, a Codex hook that reported its checker unreachable on every Estonian reply, and a response CLI that read correct Estonian as 33% Cyrillic all passed their suites, because those suites set `PYTHONUTF8=1`. The local environment answered a global question. The stdout side is still open (T-1560).
