# T-1663 -- command_resolution route budget step

Measured with `python -B tools/protocol_budget.py --summary` on 2026-10-08.

| | bytes | budget |
|---|---|---|
| before T-1663 | 54265 | 54272 |
| after the COMMANDS.md row and the REGISTRY `requires` field | 54498 | 54272 (FAIL) |
| after the step | 54498 | 55296 |

The route is REGISTRY.json plus COMMANDS.md: the command catalog an agent
reads to resolve a command. One new verb (`saipen ticket requires`) adds one
catalog row (219 bytes) and one closed ticket field (14 bytes). No other
route moves; the repository total is informational (T-1670, SRC-191 R008).

The step is one KiB, recorded here and in the T-1663 LOG chain, because the
route grows with the catalog it measures. SRC-191 R002 forbids raising the
aggregate as an answer to scarcity; this is a route budget whose values the
source leaves implementation-owned (R005), and no prose was compressed or
deleted to avoid it (R020).
