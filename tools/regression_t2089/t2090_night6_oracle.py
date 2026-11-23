"""T-2090 night-6 regression oracle: the four handoff P0 defects plus
the two adjacent live defects, as one unittest suite the canonical
`work regression` pair can anchor.

The checks are the same contracts as `t2089_p0_night6.py` (which stays
the runnable RED/GREEN report); this module wraps each check into a
TestCase so the pair executor sees an unambiguous unittest summary on
both the pre-fix and post-fix subjects.
"""

import importlib.util
import os
import sys
import unittest

# The pair executor copies the subject into a sandbox tree; the engine
# resolves its installation root from __file__ (paths.resolve_tool_root),
# so the sandbox needs the protocol documents beside it before any
# import. Copy them once from the REAL installed home, INTO THE CWD the
# executor runs in (the sandbox), never a fixed absolute path.
import shutil

_HOME = "C:/Users/vac34/AppData/Local/saipen/scheduled-source"
_PROTO_SRC = os.path.join(_HOME, "saipen")
_CWD_ROOT = os.path.abspath(os.curdir)
_SANDBOX_PROTO = os.path.join(_CWD_ROOT, "saipen")
_REPO_MARKER = os.path.join(_CWD_ROOT, "tools", "regression_t2089")
if (
    os.path.isdir(_PROTO_SRC)
    and not os.path.isdir(_REPO_MARKER)  # never copy inside the real repo
    and not os.path.isfile(os.path.join(_SANDBOX_PROTO, "BOOT.md"))
):
    shutil.copytree(_PROTO_SRC, _SANDBOX_PROTO)
os.environ.setdefault("SAIPEN_HOME", _HOME)

SUBJECT = os.path.join("tools", "saipen.py")


def _load_subject():
    spec = importlib.util.spec_from_file_location("saipen", SUBJECT)
    sys.path.insert(0, "tools")
    module = importlib.util.module_from_spec(spec)
    sys.modules["saipen"] = module
    spec.loader.exec_module(module)
    return module


def _load_journal():
    sys.path.insert(0, "tools")
    import saipen_engine.journal as journal

    return journal


class Night6ProjectionDigest(unittest.TestCase):
    """P0-A: ordered multi-chunk tail hashing in _bound_string."""

    def test_multichunk_tail_digest_order(self):
        import hashlib

        module = _load_subject()
        value = "abc" * 35000
        payload = {"ok": True, "next_action": value}
        view = module._agent_view_payload(payload)
        cuts = view.get("authority_text_truncation") or {}
        cut = next(c for c in cuts.get("cuts") or () if c.get("key") == "next_action")
        original = value.encode("utf-8")
        expected = hashlib.sha256(original[cut["kept_utf8_bytes"]:]).hexdigest()
        self.assertEqual(cut["dropped_tail_sha256"], expected)


class Night6ReceiptCapture(unittest.TestCase):
    """P0-B/C/D: identity, completeness and the read cap."""

    def test_regular_file_substitution_refused(self):
        import os
        import tempfile
        from pathlib import Path

        journal = _load_journal()
        with tempfile.TemporaryDirectory() as tmp:
            op_dir = os.path.join(tmp, "ops", "op-swap")
            os.makedirs(op_dir)
            manifest = os.path.join(op_dir, "operation.json")
            with open(manifest, "wb") as fh:
                fh.write(b"AAAA-ORIGINAL")
            replacement = os.path.join(tmp, "operation.new")
            with open(replacement, "wb") as fh:
                fh.write(b"BBBB-REPLACED")
            real_open = os.open
            state = {"swapped": False}

            def swapping_open(path, flags, *args):
                if not state["swapped"] and path == manifest:
                    state["swapped"] = True
                    os.replace(replacement, manifest)
                return real_open(path, flags, *args)

            journal.os.open = swapping_open
            try:
                entries = {
                    e.name: e
                    for e in journal._receipt_namespace_entries(Path(op_dir).parent)
                }
            finally:
                journal.os.open = real_open
            entry = entries["op-swap"]
            self.assertNotEqual(
                (entry.manifest_raw, entry.structural_error),
                (b"BBBB-REPLACED", None),
                "substituted regular-file bytes accepted as a valid capture",
            )

    def test_growth_after_fstat_refused(self):
        import os
        import tempfile
        from pathlib import Path

        journal = _load_journal()
        with tempfile.TemporaryDirectory() as tmp:
            op_dir = os.path.join(tmp, "ops", "op-grow")
            os.makedirs(op_dir)
            manifest = os.path.join(op_dir, "operation.json")
            with open(manifest, "wb") as fh:
                fh.write(b"12345678")
            real_read = os.read
            state = {"grown": False}

            def growing_read(fd, n):
                if not state["grown"]:
                    state["grown"] = True
                    with open(manifest, "ab") as fh:
                        fh.write(b"APPENDED")
                return real_read(fd, n)

            journal.os.read = growing_read
            try:
                entries = {
                    e.name: e
                    for e in journal._receipt_namespace_entries(Path(op_dir).parent)
                }
            finally:
                journal.os.read = real_read
            entry = entries["op-grow"]
            self.assertFalse(
                entry.manifest_raw == b"12345678" and entry.structural_error is None,
                "growth after fstat captured as a complete read",
            )

    def test_oversized_initial_read_capped(self):
        import os
        import tempfile
        from pathlib import Path

        journal = _load_journal()
        with tempfile.TemporaryDirectory() as tmp:
            op_dir = os.path.join(tmp, "ops", "op-cap")
            os.makedirs(op_dir)
            manifest = os.path.join(op_dir, "operation.json")
            with open(manifest, "wb") as fh:
                fh.truncate(257 * 1024 * 1024)
            with open(os.path.join(op_dir, "progress.json"), "wb") as fh:
                fh.write(b"{}")
            real_read = os.read
            biggest = {"n": 0}

            def capped_probe(fd, n):
                biggest["n"] = max(biggest["n"], n)
                return real_read(fd, min(n, 4096))

            journal.os.read = capped_probe
            try:
                for _entry in journal._receipt_namespace_entries(
                    Path(op_dir).parent
                ):
                    pass
            finally:
                journal.os.read = real_read
            self.assertLessEqual(
                biggest["n"],
                journal._RECEIPT_READ_HARD_CAP,
                "initial read requested more than the hard cap",
            )


class Night6HumanSurface(unittest.TestCase):
    """Adjacent: the human renderer must accept marker rows."""

    def test_renderer_accepts_marker_rows(self):
        import contextlib
        import io

        module = _load_subject()
        waits = ["T-1: plain row", {"byte_budget_exceeded": True, "text": "T-2: bounded"}]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            module._emit({"ok": True, "code": "STATUS_OK", "waiting_on_you": waits}, False)
        self.assertIn("T-2: bounded", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
