# T-1749: validated-project root-file scope

Status: implemented; native regression pair, neighbors and full family PASS.

`validate.py` used the running tool home's directory for its repository root
closed-set check even when `--project-root` selected a consumer. Native executed
regression creates `.stdout` and `.stderr` in that home. Independent diagnosis
(`T-1792-auto-doctor/pair-diagnosis.json`) proved those two files were the sole
blocking findings in a consumer's otherwise valid conformance run.

The check now uses the resolved `PROJECT_ROOT` for its clone-layout marker,
directory inventory, Git ignore invocation, ignore fallback and host-writer hint.
The allowed root-file set is unchanged. A generic consumer inherits no SAIPEN
root-file schema; the home validating itself, or another source checkout being
validated by this runtime, still judges that target's own root. No conformance
checks, receipt hashing, ownership or admission rules are weakened.

Three new actual-validator cases prove unchanged consumer findings despite home
spools, detection of the same stray when the home validates itself, and detection
of a stray in another source project without blaming the runtime home's stray.
The inherited Unicode locale control now validates its noisy home itself; its
original requirement (report, never crash on the Unicode name) is preserved.

Native pair `regression-execution-905ab17ed10f423b80f6e8a27459f9f3.json`:
pre-fix FAIL E-15742, post-fix PASS E-15743, identical verifier
`639372e7c1b58ff7f2ac7da982d4a8632eae69bbdfe73ae16dc9e006ac7535b7`.
The oracle and configuration are fixed across both subjects.

Additional verification: 33 layout, conformance and Auto-Doctor tests PASS
(167.502 seconds), 21 whole-source contracts PASS (22.982 seconds), pinned Ruff
0.16.0 and whitespace check PASS. The final-tree native family finished PASS:
6609 tests, zero red, E-15745, record
`core-unit/c408b3c8678817c4-20261014T233138Z.json`. The controller terminated
successfully. All six reported child PIDs were independently checked and are no
longer alive; no processes were terminated by this agent.

T-1792 stays dependency-parked at VERIFY with its own code, oracle and pre-fix
subject preserved. Resume its original native regression after T-1749's complete
verification, review and local no-publish finish. The wider SRC-253 mission and
remaining cc all queue stay open.
