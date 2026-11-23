# T-1956 BUILD -- repoint the desktop probe at the artifact that exists

## Change

One file: `tools/test_host_bootstrap.py`. The old `test_32` extracted
`loadUserKnowledgeFiles` -- a **home** scanner -- and asserted that
`~/.AGENTS.md` reached the desktop prompt. That function is gone from the
shipped bundle. The replacement executes the loader that is actually there and
asserts the contract that actually holds.

Extracted into `_desktop_instruction_probe(self) -> Path` so the probe can be
inspected and reused; the test body then makes three measurements.

### The probe

- Takes the **loader name as an argument** rather than grepping for one fixed
  symbol. That is what makes the red control possible: point it at a name the
  bundle never defines and it must fail loudly.
- Anchors from `function isFile(` (the helper the loader uses) to the next
  top-level `function `, so the slice self-terminates instead of relying on a
  second magic symbol name.
- Injects only the names the slice actually references (`join\d+`,
  `readFileSync\d+`, `statSync\d+`, `relative\d+`), each mapped to the real
  `path`/`fs` function. Anything the slice forgot would surface as a
  `ReferenceError`, not a quiet empty answer.
- Reads `PROJECT_INSTRUCTION_LIMIT` and `PROJECT_INSTRUCTION_TRUNCATION_NOTE`
  **out of the bundle** by regex instead of hardcoding them. Hardcoding would
  let the probe keep answering an old bound after the host moved it -- the same
  drift class this test exists to catch. A missing bound is
  `EXTRACT_FAILED:<name>`, exit 3.

### The three legs

1. **Delivery.** A project root whose `AGENTS.md` carries the block must come
   back with `<!-- SAIPEN:BEGIN -->` and `cc` in it. Measured: 4,242 bytes
   delivered, head `\n\nProject instructions loaded by Freebuff:\n\nInstructions
   from AGENTS.md:\n\n...`.
2. **The dropped surface.** A home carrying *only* `.AGENTS.md` must be
   delivered to **nothing**. This is the assertion that stops the old home
   contract from being believed again by a future reader.
3. **The extractor cannot pass vacuously.** Pointed at
   `loadUserKnowledgeFiles`, the probe must exit non-zero with
   `EXTRACT_FAILED`. Without this, leg 2's `assertEqual(..., "")` would also be
   satisfied by a probe that extracted nothing and returned "" for the wrong
   reason.

## Measured results

```
$ python -B -m unittest tools.test_host_bootstrap
Ran 25 tests in 14.006s
OK

$ (three-leg direct probe)
1. green subject:   Project instructions loaded by Freebuf...
2. old symbol -> rc 3 | EXTRACT_FAILED:loadUserKnowledgeFiles
3. bundle stops delivering -> delivered  '\n\nProject instructions loaded by Freebuff:...'
   block absent: True
```

Leg 3's second part is the oracle check: when the fixture `AGENTS.md` holds no
block, the loader still returns its wrapper text but without
`<!-- SAIPEN:BEGIN -->`, so the test's `assertIn` reds on the assertion that
matters rather than on an unrelated string.

## What BUILD deliberately did not change

`extensions/adapters/registry.json:487-493` still declares the FreeBuff Desktop
loader surface as `["~/.AGENTS.md", "~/.CLAUDE.md"]`, and
`autoinject.instruction_contract_status(...)` therefore still reports
`status: current` for this machine on the strength of `~/.AGENTS.md` existing.

Changing that is a **registration-strategy decision**, not a test repair:

- the shipped desktop bundle reads the **project root**, and this repository has
  no root `AGENTS.md` (`saipen host instructions status` →
  `PROJECT_BLOCK_ABSENT`), so the honest declaration is either "the desktop
  surface is the project root" or "this host no longer receives home activation"
  -- those imply different installer behaviour;
- `test_instruction_loader_contracts.test_the_registry_declares_the_measured_loader_contracts`
  asserts those exact lists, so the change carries its own contract and its own
  red control;
- whatever is chosen, it is a behaviour change for every project on this host,
  not just this repository.

Filing that as its own ticket keeps this one's verify text honest: T-1956 says
"the test measures the surface that exists", not "the host registration is
correct". SCOUT recorded the finding so it is not lost.
