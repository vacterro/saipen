"""Shared lexical roles for shell-decoded SAIPEN option operands."""

from __future__ import annotations

from collections.abc import Collection, Sequence


VALUE_OPTIONS = frozenset({
    "--action", "--adapter", "--admission-session", "--adopt-legacy", "--agent",
    "--amends", "--apply-approved-repair", "--attempted-condition",
    "--attest-legacy-done", "--authority", "--authority-root", "--body",
    "--budget", "--by", "--cap", "--caps-file", "--carrier-hex", "--carrier-json",
    "--category", "--class", "--closure-cohort", "--closure-mode", "--cohort",
    "--contract", "--cwd", "--days", "--delta", "--detail-mode", "--discovery-event",
    "--environment", "--event-cwd", "--event-json", "--evidence", "--executor",
    "--field", "--file", "--fixed-by", "--gate", "--handoff", "--helper-reason",
    "--hex", "--home", "--host", "--host-lineage", "--host-root", "--implementation",
    "--implementation-source", "--include-hex", "--invalidated-by", "--item-id",
    "--k", "--keep", "--kind", "--label", "--max-files", "--max-matches", "--model",
    "--needs", "--note", "--operation-id", "--package", "--paths", "--priority",
    "--producer", "--profile", "--project-root", "--provider", "--python",
    "--reason", "--reassign", "--rebuild-command", "--receipt", "--recurrence",
    "--regression", "--replacement", "--report", "--reproduced", "--request",
    "--resolution", "--resolve-duplicate-id", "--retry_not_before", "--role",
    "--root", "--run", "--runtime", "--runtime-info", "--scope", "--scope-hex",
    "--session", "--sha256", "--slice", "--successor", "--supersedes", "--task-class",
    "--ticket", "--timeout", "--to", "--unknown", "--verification", "--verify",
    "--weak-model", "--when-environment", "--work", "--workspace",
})


def option_value_positions(argv: Sequence[str]) -> set[int]:
    """Locate opaque operands before interpreting any global option or `--`."""
    positions: set[int] = set()
    index = 0
    while index < len(argv):
        if argv[index] == "--":
            break
        if argv[index] == "--text":
            # audit enqueue owns the complete remaining body, not just one
            # word; its grammar does not interpret later switches either.
            positions.update(range(index + 1, len(argv)))
            break
        if argv[index] in VALUE_OPTIONS and index + 1 < len(argv):
            positions.add(index + 1)
            index += 2
        else:
            index += 1
    return positions


def has_option(argv: Sequence[str], options: Collection[str]) -> bool:
    """Only an unconsumed token before the real boundary is a switch."""
    values = option_value_positions(argv)
    for index, token in enumerate(argv):
        if index in values:
            continue
        if token == "--":
            break
        if token in options:
            return True
    return False
