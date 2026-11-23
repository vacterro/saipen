# T-1373 SHIP -- two repositories, one committed, one blocked

## SAIPEN (this repository) -- COMMITTED

    commit d4bb4738  fix(audit): a proof the contract never declared does not
                     survive its own regeneration

48 paths, all T-1373's: the generator and its tests, this evidence directory,
the project's own regenerated `.saipen/MANIFEST.json`, the SRC-054 receipt with
its contract and settled coverage, the intake index entry, and the canonical
BOARD/LOG/STATE checkpoints. Nothing else was staged: the working tree still
carries other tickets' untracked evidence directories (T-1327, SAIPAL) and
~30 older untracked SRC bodies, and none of them entered this commit.

No push. No tag. No release.

## AUDAPACK (V:\___VAC\__K\__CODE\_PY\_AUDAPACK) -- NOT COMMITTED, BLOCKED

    HEAD    38a7cc48  chore(saipen): close SRC-038 and T-160 on the board
    branch  main

T-1373 owns exactly two files there:

    audapack/saipen_evidence.py        mtime 2026-09-16 23:36:20
    tests/test_saipen_evidence.py      mtime 2026-09-16 23:36:01

Both are byte-identical to the copies inside `_AUDAPACK_16.09.26-T23-41-20.zip`
(sha256 bfca5fe10624373df3f285d68ebf25e2.. and 3cf4ca4980d4e2194ba6fc36de87acdb..),
so the consumer measured in VERIFY is the consumer on disk: nothing drifted
since E-6839.

The commit is blocked, and not by a judgement call:

1. **Both owned files are UNTRACKED** in that repository (`git check-ignore`
   returns nothing, so they are not ignored -- simply never committed). A
   narrow `git add` of those two paths would not commit T-1373's change; it
   would commit each file whole, including everything written into them before
   this ticket existed.
2. **The tree is foreign-dirty**: 52 modified tracked files and ~150 untracked
   paths, none of them T-1373's -- bridge, UI, packing, widget tests, SAIHANDOFF
   documents from 2026-09-10, opencode work.
3. **Another agent holds the seat.** AUDAPACK's own BOARD has
   `T-194 [P1] ... owner: buffy | claim_time: 2026-09-16T19:24:45Z` in DOING,
   and files were edited there during that claim (resources/AUDAPACK_WIDGET.user.js
   22:34, scripts/probe_chatgpt_live.py 22:43, tests/widget/w6-006 22:31), plus
   its own SRC-049/SRC-050 intake. Committing another owner's uncommitted work
   is not this ticket's move.

What IS proven about that side, from current bytes:

    focused  tests/test_saipen_evidence.py   1 failed, 49 passed
             (the one red is BASELINE -- see
             verify-audapack-known-failure-attribution.txt)
    full     python -m pytest                8 failed, 1740 passed, 5 skipped
             identical failing identities to the pre-change baseline
             PATCH_OWNED = 0, UNKNOWN = 0, passed 1727 -> 1740 (+13 new cases)

**Exact blocker to lift**: AUDAPACK's owner commits (or explicitly releases)
its own dirty work, after which `audapack/saipen_evidence.py` and
`tests/test_saipen_evidence.py` can be committed there as one narrow
cited-evidence consumer commit. The files stay in place, untouched, until then.
