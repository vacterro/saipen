"""T-1665: the guard admits the two documented phase verbs and never calls a verb a non-verb.

Usage: patch_t1665.py <tree-root>   (asserts every anchor occurs exactly once)
"""
import json
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])


def patch(rel: str, edits: list[tuple[str, str]]) -> None:
    path = ROOT / rel
    raw = path.read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8").replace("\r\n", "\n")
    for old, new in edits:
        assert text.count(old) == 1, (rel, text.count(old), old[:80])
        text = text.replace(old, new)
    path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
    print("patched", rel, "crlf" if crlf else "lf")


patch("saipen/COMMAND_EFFECTS.json", [(
    '''  "not_shell_canonical": [
    "init",
    "clean",
    "translate",
    "first-publish-confirm",
    "launch"
  ],
''',
    '''  "not_shell_canonical": [
    "init",
    "first-publish-confirm",
    "launch"
  ],
''',
)])
json.loads((ROOT / "saipen/COMMAND_EFFECTS.json").read_text(encoding="utf-8-sig"))

patch("tools/saipen_engine/command_effects.py", [(
    '''def routed_verb(token: str, rest: Sequence[str] = ()) -> str:
''',
    '''def is_known_verb(token: str, rest: Sequence[str] = ()) -> bool:
    """Whether `saipen <token> <rest...>` names a verb the CLI dispatches at
    all -- shell-canonical or not (T-1665)."""
    return token in _VERBS or routed_verb(token, rest) in _VERBS


def routed_verb(token: str, rest: Sequence[str] = ()) -> str:
''',
)])

patch("tools/saipen_engine/guard_events.py", [
(
    '''def saipen_line_problem(command: str | None) -> tuple[str, str | None] | None:
''',
    '''#: A verb the CLI dispatches but a shell line never runs as one canonical
#: operation, with what is true about it and the spelling that IS admitted
#: (T-1665: the guard used to call these "not a verb", which they are).
_NOT_FROM_A_SHELL = {
    "init": (
        "`saipen set` is the same command and is admitted from a shell",
        "saipen set",
    ),
    "launch": (
        "it starts a host process, which the operator runs from their own shell, "
        "never from inside a host session",
        None,
    ),
    "first-publish-confirm": (
        "it records the operator's own publication consent, which an agent never types",
        None,
    ),
}


def saipen_line_problem(command: str | None) -> tuple[str, str | None] | None:
'''),
(
    '''        if not command_effects.is_shell_canonical_verb(verb, words[2:]):
            import difflib
''',
    '''        if not command_effects.is_shell_canonical_verb(verb, words[2:]) and (
            command_effects.is_known_verb(verb, words[2:])
        ):
            routed = command_effects.routed_verb(verb, words[2:])
            truth, spelling = _NOT_FROM_A_SHELL.get(
                routed, ("this route admits no shell spelling of it", None)
            )
            return (
                f"`saipen {verb}` is a SAIPEN verb this guard does not run from a "
                f"shell line: {truth}",
                spelling,
            )
        if not command_effects.is_shell_canonical_verb(verb, words[2:]):
            import difflib
'''),
])
