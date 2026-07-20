# SAIPEN Conformance

Implementations MUST pass self-check across three vectors:
1. **Repo Validation**: `STATE.md`, `BOARD.md`, `LOG.md`, and `KNOWLEDGE/` MUST conform to the shapes RFC.md § 1.2 defines, enforced today by `tests/validate.sh` / `validate.ps1`. `extensions/schemas/*.json` are a forward-looking reference for a future external validator, not machine-enforced yet -- see `extensions/schemas/README.md`.
2. **Session Validation**: `BOARD.md` MUST be acyclic. `LOG.md` graph parent-child links MUST resolve.
3. **Phase Contract Validation**: Stated `mode` MUST legally permit the current `phase`.

## TEST-001: The Continuation Test
Any release of this protocol MUST pass the gold standard test:
1. Cold agent (zero chat history).
2. Execute `saipen continue` (or equivalent bootstrap command).
3. Agent MUST: read `next_action` and execute it instantly WITHOUT asking for context.
If the agent asks "What should I do?", the protocol has failed.
