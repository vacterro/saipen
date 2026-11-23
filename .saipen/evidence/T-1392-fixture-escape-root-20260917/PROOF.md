# Why SRC-059/060 and T-1390/T-1391 were minted into MAIN

Measured 2026-09-17, this project, protocol 8.0.1.

## The escape path, exactly

`tools/test_session_binding.py:217` launches the real CLI in a fixture:

    env = dict(os.environ)            # the WHOLE host environment
    env.pop(HOST_SESSION_ENV, None)   # only the session id is stripped
    subprocess.run([sys.executable, SAIPEN, "start",
                    "add a trailing comment", "--json"],
                   cwd=str(project), env=env, ...)

`cwd` says fixture. The environment still says MAIN, because
`SAIPEN_PROJECT_ROOT` survives the copy, and
`tools/saipen_engine/paths.py:557` ranks that carrier ABOVE the working
directory:

    1. explicit --project-root
    2. SAIPEN_PROJECT_ROOT / SAIPEN_PROJECT_LINEAGE   <-- wins here
    3. Git worktree
    4. Git common/main worktree
    5. nearest ancestor .saipen

So the fixture's own `cwd` is never consulted. `saipen start` binds to the
carrier's project and mints there.

## Live reproduction

Two stand-in projects built with the existing isolation owner's builder
(`tools/test_field_fixture_isolation.py::make_project`), the call shape copied
verbatim from `test_session_binding.py:217`:

    start code            : STARTED
    bound root            : ...\saipen-repository-bc0_igfl\repository
    receipt/ticket        : SRC-001 T-1
    cwd (fixture)         : ...\saipen-fixture-gsyrai5y\fixture
    SAIPEN_PROJECT_ROOT   : ...\saipen-repository-bc0_igfl\repository
    WRONG project mutated : True
    fixture  mutated      : False
    wrong-project tickets : ['T-1'] receipts: 1

The fixture is untouched. The project named by the inherited carrier gets the
receipt, the ticket and the canonical events. That is SRC-060 / T-1391
("add a trailing comment") byte-for-byte, and the SRC-059 / T-1390 family is
the same call shape with the docstring payload.

## Why the fixture called `start` at all

At the closure commit 8cd798cc the seat gate was RED:

    tools.test_session_binding -> Ran 17, FAILED (failures=3)
    AssertionError: 'STARTED' != 'WAIT_FOREIGN_OWNER'

so the fixture's `start` was NOT refused; it ran to completion and minted.
With the intended `entry.py` bytes (T-1388) the same family is:

    tools.test_session_binding -> Ran 17, OK

Two independent defects had to line up: a carrier that out-ranks `cwd`
(this file) and a seat gate that did not refuse (T-1388).

## Same class as T-1370, different carrier

`tools/test_field_fixture_isolation.py` already owns this invariant for `PWD`
(SRC-047/T-1368, SRC-048/T-1369, 16.09.26). The carrier changed; the class did
not. The fix belongs to that owner, not to a new sanitizer.

Note the irony already in the tree: that owner's own
`run_stand_in_host` strips `SAIPEN_PROJECT_ROOT`, `SAIPEN_PROJECT_LINEAGE` and
`SAIPEN_SKILL_ROOT` by hand. The knowledge existed; it was one file's private
habit instead of one enforced invariant.
