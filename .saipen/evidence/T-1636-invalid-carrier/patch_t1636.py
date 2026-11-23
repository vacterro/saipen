"""T-1636: an invalid carrier never hides the project the session is in.

Usage: patch_t1636.py <tree-root>   (asserts every anchor occurs exactly once)
"""
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


SHORTCUT = '''    declared = os.environ.get("SAIPEN_PROJECT_ROOT", "").strip()
    if declared:
        try:
            root = Path(declared).resolve()
            return root if (root / ".saipen" / "STATE.md").is_file() else None
        except OSError:
            return None
'''
BOUND = '''    declared = os.environ.get("SAIPEN_PROJECT_ROOT", "").strip()
    if declared:
        try:
            root = Path(declared).resolve()
        except OSError:
            root = None
        if root is not None and (root / ".saipen" / "STATE.md").is_file():
            return root
        # T-1636: a carrier that names nothing usable never hides the project
        # the session directory belongs to. The walk below finds it, and the
        # engine judges the carrier from there (BINDING_CARRIER_INVALID).
'''

patch("extensions/adapters/claude/saipen-guard.py", [
(
'''    Explicit ``SAIPEN_PROJECT_ROOT`` wins; otherwise the nearest ancestor of the
    session cwd carrying canonical STATE. No project means no SAIPEN context at
    all, and the event is ordinary chat. This is only the cheap question "is
    there a project here at all": whether a carrier CONTRADICTS the project is
    the binding owner's decision, made by the engine from the event cwd.''',
'''    An explicit ``SAIPEN_PROJECT_ROOT`` naming a project wins; otherwise the
    nearest ancestor of the session cwd carrying canonical STATE. No project
    means no SAIPEN context at all, and the event is ordinary chat. This is
    only the cheap question "is there a project here at all": whether a
    carrier CONTRADICTS the project is the binding owner's decision, made by
    the engine from the event cwd.'''),
(SHORTCUT, BOUND),
(
'''    if project is None:
        if os.environ.get("SAIPEN_PROJECT_ROOT", "").strip():
            record(
                BOUNDARY_UNAVAILABLE.format(
                    reason="explicit SAIPEN_PROJECT_ROOT is not a bound SAIPEN project"
                )
            )
        # No SAIPEN project: ordinary non-operational chat.
        return 0
''',
'''    if project is None:
        # No SAIPEN project, whatever a carrier says: ordinary chat (T-1636).
        return 0
'''),
])

patch("extensions/adapters/codex/saipen-guard.py", [
(
'''    Explicit ``SAIPEN_PROJECT_ROOT`` wins; otherwise the nearest ancestor of
    the session cwd carrying canonical STATE.''',
'''    An explicit ``SAIPEN_PROJECT_ROOT`` naming a project wins; otherwise the
    nearest ancestor of the session cwd carrying canonical STATE.'''),
(SHORTCUT, BOUND),
(
'''    if project is None:
        if os.environ.get("SAIPEN_PROJECT_ROOT", "").strip():
            record(
                BOUNDARY_UNAVAILABLE.format(
                    reason="explicit SAIPEN_PROJECT_ROOT is not a bound SAIPEN project"
                )
            )
            return 0
        # No SAIPEN project: ordinary non-operational chat.
        return 0
''',
'''    if project is None:
        # No SAIPEN project, whatever a carrier says: ordinary chat (T-1636).
        return 0
'''),
])


# The two tests that pinned the shortcut this ticket removes.
patch("tools/test_codex_stop_hook.py", [(
"""    def test_invalid_explicit_project_binding_does_not_fall_back_to_cwd(self):
        project = wait_project()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
            os.environ, {"SAIPEN_PROJECT_ROOT": tmp}
        ):
            rc, out, _ = stop_event(project, "STATUS: probe")
        self.assertEqual(rc, 0, out)
        self.assertNotIn("decision", out)
        self.assertIn("explicit SAIPEN_PROJECT_ROOT", out["systemMessage"])
""",
"""    def test_an_invalid_carrier_never_hides_the_session_project(self):
        # T-1636: a carrier that names nothing usable used to turn this Stop
        # into ordinary chat. The session's own project is gated instead.
        project = wait_project()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
            os.environ, {"SAIPEN_PROJECT_ROOT": tmp}
        ):
            rc, out, _ = stop_event(project, "Everything is fine.")
        self.assertEqual(rc, 0, out)
        self.assertEqual(out["decision"], "block")
        self.assertIn("INVALID_OPERATIONAL_PROSE", out["reason"])
"""),
])

patch("tools/test_t1624_host_integration.py", [(
r"""        noisy = self.tmp / "noisy.py"
        noisy.write_text(
            HOOK.read_text(encoding="utf-8").replace(
                "    if project is None:\n        if os.environ.get",
                "    if project is None:\n        print('{}')\n        if os.environ.get",
            ),
            encoding="utf-8",
        )
""",
r"""        noisy = self.tmp / "noisy.py"
        anchor ="    if project is None:\n        # No SAIPEN project"
        self.assertIn(anchor, HOOK.read_text(encoding="utf-8"), "the red control's anchor moved")
        noisy.write_text(
            HOOK.read_text(encoding="utf-8").replace(
                anchor, "    if project is None:\n        print('{}')\n        # No SAIPEN project"
            ),
            encoding="utf-8",
        )
"""),
])
