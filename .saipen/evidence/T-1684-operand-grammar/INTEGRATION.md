# T-1684 shared operand grammar candidate

The live CLI retains Core ownership. No source or canonical phase change for
T-1684 has been applied. candidate/ and owned-review.patch contain five scoped
paths. baseline.json captures the exact inherited T-1631 implementation; match
it before copying files. If later tickets edit any of these paths, rebase the
scoped patch in an isolated copy and rerun the held verifier. Never replace
newer unrelated bytes with the saved candidate.

cli_grammar.py owns the existing scalar option inventory and the variadic
--text boundary. The CLI, compound splitter and effect classifier share those
roles. Literal +, -- and --help stay operands, actual control tokens retain
their effect, and the classifier agrees with the operation the CLI dispatches.
The grammar is an ordinary tools/ module already covered by the runtime tree;
no extra protocol data file or MANIFEST change is needed.

The final fixed 16-test oracle is red on the exact pre-task implementations,
green on the candidate, and green in an unmodified clone control (pair.json):
verifier 46384e17d5ccef46, pre ef37ed7e1fdb23d1, post ff3dc5125f8dd1bf.
It exercises real CLI values and literal-help ticket writes, with a read-only
inverse retaining zero writes. The eight existing T-1631 tests also pass.
Additional checks passed: 37 source contracts; nine command-effect controls
plus the real bundled-interpreter projection; all eight compound CLI tests;
Ruff 0.16.0 on tools/ and tests/.

Current-tree full-family evidence and canonical VERIFY/REVIEW/SHIP are still
required after integration. This is a prepared candidate, not DONE. The earlier
six-path T-1631 alternative was rejected; do not apply that package.
