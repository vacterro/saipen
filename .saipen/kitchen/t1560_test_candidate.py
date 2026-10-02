"""Prepare and exercise a permanent UTF-8 inventory/control oracle in isolation."""
from __future__ import annotations

import ast
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DRAFT = ROOT / ".saipen/evidence/T-1560-utf8-candidate"
builder = ROOT / ".saipen/kitchen/t1560_utf8_candidate.py"
raw = builder.read_text(encoding="utf-8")
tree = ast.parse(raw)
functions = "\n\n".join(ast.get_source_segment(raw, node)
                        for node in tree.body if isinstance(node, ast.FunctionDef)
                        and node.name in {"production_files", "sites", "decoding_probe"})
test = '''"""Text-mode production subprocesses must decode the declared UTF-8 contract."""
from __future__ import annotations

import ast
import copy
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
FUNCTIONS = {"run", "Popen", "check_output", "check_call", "call"}

''' + functions + '''


class SubprocessUtf8Contract(unittest.TestCase):
    def test_no_production_text_call_uses_the_implicit_locale(self):
        missing = []
        for path in production_files():
            for node, name, keywords, _text_kw in sites(path.read_text(encoding="utf-8")):
                if "encoding" not in keywords:
                    missing.append(f"{path.relative_to(ROOT)}:{node.lineno}: {name}")
        self.assertEqual(missing, [], "explicit child-output encoding is required")

    def test_utf8_sites_preserve_a_real_child_output_under_cp1251(self):
        checked = 0
        for path in production_files():
            for node, name, keywords, _text_kw in sites(path.read_text(encoding="utf-8")):
                encoding = keywords.get("encoding")
                if encoding is None or not isinstance(encoding.value, ast.Constant):
                    continue
                if encoding.value.value != "utf-8":
                    continue
                with self.subTest(path=str(path.relative_to(ROOT)), line=node.lineno):
                    self.assertTrue(decoding_probe(node, name, keywords))
                checked += 1
        self.assertGreater(checked, 0, "the decoding oracle tested no production site")

    def test_missing_encoding_red_control_really_corrupts_utf8(self):
        call = ast.parse("subprocess.run(['unused'], text=True)", mode="eval").body
        self.assertFalse(decoding_probe(call, "run"))

    def test_dict_built_text_settings_are_part_of_the_inventory(self):
        source = "def child():\\n    options = dict(text=True)\\n    subprocess.run([], **options)\\n"
        before = list(sites(source))
        after = list(sites(source.replace("text=True", 'text=True, encoding="utf-8"')))
        self.assertEqual(len(before), 1)
        self.assertNotIn("encoding", before[0][2])
        self.assertIn("encoding", after[0][2])
        self.assertFalse(decoding_probe(before[0][0], before[0][1], before[0][2]))
        self.assertTrue(decoding_probe(after[0][0], after[0][1], after[0][2]))

    def test_unknown_forwarded_settings_are_not_silently_excluded(self):
        source = "def child(options):\\n    subprocess.run([], **options)\\n"
        with self.assertRaisesRegex(ValueError, "unreviewed subprocess kwargs"):
            list(sites(source))

    def test_import_aliases_are_in_the_same_inventory(self):
        source = (
            "import subprocess as child\\n"
            "from subprocess import Popen as spawn\\n"
            "child.run([], text=True)\\n"
            "spawn([], universal_newlines=True)\\n"
        )
        self.assertEqual({name for _node, name, _kw, _text in sites(source)}, {"run", "Popen"})


if __name__ == "__main__":
    unittest.main()
'''
formatted = subprocess.run([sys.executable, "-B", "-m", "ruff", "format",
                            "--stdin-filename", "tools/test_subprocess_utf8.py", "-"],
                           input=test.encode("utf-8"), capture_output=True, cwd=ROOT, check=True).stdout
(DRAFT / "test_subprocess_utf8.py.draft").write_bytes(formatted)
lint = subprocess.run([sys.executable, "-B", "-m", "ruff", "check",
                      "--stdin-filename", "tools/test_subprocess_utf8.py", "-"],
                     input=formatted, capture_output=True, cwd=ROOT)
if lint.returncode:
    raise RuntimeError(lint.stdout.decode("utf-8"))
namespace = {"__file__": str(ROOT / "tools/test_subprocess_utf8.py"), "__name__": "utf8_candidate"}
exec(compile(formatted, namespace["__file__"], "exec"), namespace)
if "--candidate" in sys.argv:
    sandbox = tempfile.TemporaryDirectory(prefix="saipen-utf8-oracle-")
    sandbox_root = Path(sandbox.name)
    manifest = json.loads((DRAFT / "manifest.json").read_text(encoding="utf-8"))
    for source in namespace["production_files"]():
        relative = source.relative_to(ROOT)
        target = sandbox_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    for record in manifest["files"]:
        relative = record["path"]
        target = sandbox_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((DRAFT / (relative + ".draft")).read_bytes())
    namespace["ROOT"] = sandbox_root
output = io.StringIO()
suite = unittest.defaultTestLoader.loadTestsFromTestCase(namespace["SubprocessUtf8Contract"])
result = unittest.TextTestRunner(stream=output, verbosity=1).run(suite)
if "--candidate" in sys.argv:
    sandbox.cleanup()
print(output.getvalue())
proof = {"oracle_sha256": hashlib.sha256(formatted).hexdigest(),
         "scope": "all inventoried text-mode subprocess calls, including local dict-built kwargs; unknown settings refuse",
         "status": "PASS" if result.wasSuccessful() else "FAIL", "tests": result.testsRun,
         "failures": len(result.failures), "errors": len(result.errors), "output": output.getvalue()}
(DRAFT / ("permanent-oracle-green.json" if "--candidate" in sys.argv else "permanent-oracle-red.json")).write_text(
    json.dumps(proof, indent=2) + "\n", encoding="utf-8")
sys.exit(0 if result.wasSuccessful() else 1)
