# Scenario fixtures

Each subdirectory is one test case. The runner copies its `.saipen/` tree
into a temp project and runs `tools/validate.py` against it.

**Format:**
- First line of `README.md`: `expect: pass` or `expect: fail`
- `expect: pass` → validator must exit 0 (conformant)
- `expect: fail` → validator must exit non-zero with the scenario's
  declared failure slug in the output

**Structure:**
```
<name>/
  README.md          # expect: pass|fail line + description
  .saipen/
    STATE.md         # initial state for the test
    BOARD.md         # must have all 4 headings (## DOING, TODO, BLOCKED, DONE)
    LOG.md           # at least one E-1 event
    extensions/subs/ # optional: subSaipen instances
      <sub>/
        STATE.md     # subSaipen's own state (mode: read-only required)
        BOARD.md
        LOG.md
        kitchen/
          OUTBOX.md  # optional: handoff package
```

Every STATE.md at schema_version 3 needs `last_event` when its LOG is
non-empty, and `style_contract` matching STYLE.md's marker. Every LOG
needs at least one RFC §1.2 skeleton line (DATE [E-###] TAXONOMY: text).
