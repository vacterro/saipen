<!-- SAIPEN KNOWLEDGE CARD v1 -->
kind: trap
scope: tools/saipen_engine/core_unit.py, tools/saipen_engine/install_identity.py, bin/saipen, bin/saipen.cmd, test_t1627_operator_question, test_t1645_zero_hunt, declared core-unit family
trigger: a single-process (`--jobs 1`) family red on the four t1627 real-transport tests and/or the two t1645 launcher tests, or any core-unit run started while the home tree is still being edited
status: active
evidence: T-1824, T-1823, .saipen/evidence/core-unit/f1c56a2fc1144fb7-20261019T125009Z.json, tools/saipen_engine/install_identity.py, tools/test_t1627_operator_question.py:223, tools/test_t1645_zero_hunt.py:154
supersedes: none

# A copied tree runs the live engine through a pinned launcher

The generated `bin/saipen` and `bin/saipen.cmd` contain the absolute path of the home that generated them; `copy_tree_consistent` copies those files verbatim, so a sandbox invokes the LIVE `tools/saipen.py`, and both directions of the mismatch read as `home-divergent`: t1627 runs the copy's engine while its fixture STATE inherits the live `saipen_home:` line, and t1645 launches the pinned live engine while its fixture STATE names the copy.

Why:
`install-v1` covers `saipen/*.md`, `saipen/*.json`, `saipen/phases/*.md` and every `tools/**/*.py` (`tools/saipen_engine/install_identity.py`). Before the copy and the live home are byte-identical, both spellings compare equal and all six tests pass. One write to any covered file while the family runs makes them differ, and every later gate that compares them refuses (`BLOCKED`, `INVALID_OPERATIONAL_PROSE: no canonical operator decision is due`, `home-dead: home-divergent`). The failure paths point into the sandbox, so the reds look like a coupling defect in the tests.

Measured: the 5117 s `--jobs 1` run `f1c56a2fc1144fb7-20261019T125009Z` reported 6925 tests, 6 new red -- exactly these six -- after one `tools/` edit landed mid-run (running install `install-v1:4a73...`, copied tree `install-v1:594c...`). Controlled repro, no prefix modules needed: copy the tree with `core_unit.new_sandbox_root` + `copy_tree_consistent`, append one comment to the copy's `tools/test_freebuff_operator_provenance.py`, then run `python -B -m unittest discover -s tools -p "test_t1627*.py"` (4 failures) and `-p "test_t1645*.py"` (2 failures) in the copy; the messages are identical. Removing the comment makes both modules green (23 and 7 tests).

Rule: treat `saipen/**/*.md`, `saipen/**/*.json` and `tools/**/*.py` as read-only for the whole duration of a family run. A red on these six names after such an edit is observer drift; restore byte equality and rerun on the unchanged tree. Do not adjust these tests or the baseline to accommodate it.
