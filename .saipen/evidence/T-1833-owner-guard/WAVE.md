# Verification ownership boundary — T-1833

The POSIX verification launcher starts an isolated Python bootstrap in an owned
process group. It waits until the parent has recorded reader ownership before
executing the verifier. A guardian watches a parent-owned pipe and kills that
same group when the owner dies. The guardian retains neither verifier output
nor user descriptors. Windows retains suspended creation, job assignment and
kill-on-job-close; ordinary host commands retain the existing launch path.

Two failure paths were found and corrected during this Work:

* `Popen` failure leaked the bootstrap pipe's read descriptor. Validation now
  precedes allocation, and launch/error cleanup closes both pipe ends.
* Interruption of a direct STARTING ownership-stamp write could leave truncated
  JSON and prevent recovery. STARTING now uses the same existing atomic writer
  as reader registration. No alternate ownership ledger was added.

Independent controls execute real processes on Linux under WSL
`saipen-posix`, Python 3.12.13. They cover registration before verifier code,
registration refusal, owner death before and after registration, descendant
cleanup, preservation of an unrelated process, user-pipe/output EOF, launch
failure cleanup, interrupted stamp writes, and actual single-flight recovery
after killing a running canonical family's owner. The recovery test executes
a fresh verifier and deliberately publishes no synthetic verification receipt.

`check_pair.py` copies the small runtime package into private temporary
subjects, substitutes only the saved prefix implementations, and runs the
byte-identical test module and command for both subjects. `regression-pair.json`
binds the oracle and implementation hashes; the prefix fails on the descriptor
leak and torn stamp, and the corrected runtime passes. The separate
`check_spawn_stamp.py` demonstrates a real subprocess dying during the old
direct write; prefix-stamp.log and postfix-stamp.log preserve its verdicts.

The pre-existing process-tree module passed its six controls on both Windows
and Linux. The parent single-flight module passed all 18 controls on Windows
(42.045 s) and Linux (7.532 s), including three real CLI consumers sharing one
execution and propagation of the same failed execution to every consumer.
These timings are different platforms and are not a speedup comparison.
The initial canonical focused source-contract run passed 33 tests; subsequent
canonical receipts and exact final revision are recorded in LOG.

This is a correctness prerequisite for T-1832. No aggregate verification-time
saving, whole-suite improvement, campaign completion, macOS acceptance or
publication is claimed. Supported proc-based POSIX behavior was executed on
Linux; required final full-family and release gates remain owed by the batch.
Rollback sources are under `prefix/`; preserve unrelated accumulated changes.

This wave completed locally into pending C-007. T-1834 resolved the real
cross-tool-call environment refusal before SHIP; both consumers cited the same
13-check execution independently. T-1832 subsequently fixed the observed P2
orphan guard directory path, verified its own 93-check package and completed
locally into C-009. Historic residue was preserved. Next: resumed T-1829's
remaining tier/impact/CI/economics and final acceptance requirements.
