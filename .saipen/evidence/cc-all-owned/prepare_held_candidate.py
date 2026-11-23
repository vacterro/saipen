"""Prepare an isolated startup-readiness repair; never edit the live test."""
import ast
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
source = (ROOT / "tools/test_t1505_core_unit_sandbox_reclaim.py").read_text(encoding="utf-8")
before = HERE / "held_fixture.before.py"
if before.exists():
    assert before.read_text(encoding="utf-8") == source, "live subject changed; do not overwrite saved original"
else:
    before.write_text(source, encoding="utf-8")
tree = ast.parse(source)
subject = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "HeldSandboxTests")
hold = next(node for node in subject.body if isinstance(node, ast.FunctionDef) and node.name == "hold")
lines = source.splitlines(keepends=True)
replacement = '''    def hold(self, cwd: Path, seconds: float = 30.0) -> subprocess.Popen:
        holder = subprocess.Popen(
            [sys.executable, "-c", self.HOLD], cwd=cwd,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.addCleanup(holder.stdin.close)
        self.addCleanup(holder.stdout.close)
        self.addCleanup(holder.stderr.close)
        self.addCleanup(holder.wait)
        self.addCleanup(holder.kill)
        ready = queue.Queue()
        reader = threading.Thread(target=lambda: ready.put(holder.stdout.readline()), daemon=True)
        reader.start()
        try:
            signal = ready.get(timeout=seconds)
        except queue.Empty:
            self.fail("the holder did not signal startup before the bound")
        self.assertEqual(signal.strip(), b"READY", "the holder failed before startup")
        self.assertIsNone(holder.poll(), "the holder exited before the test owns its lifetime")
        return holder
'''
lines[hold.lineno - 1:hold.end_lineno] = [replacement]
candidate = "".join(lines)
candidate = candidate.replace("import json\n", "import json\nimport queue\nimport threading\n", 1)
assert '    HOLD = "import time; time.sleep(float(__import__(\'sys\').argv[1]))"' in candidate
candidate = candidate.replace(
    '    HOLD = "import time; time.sleep(float(__import__(\'sys\').argv[1]))"',
    '    HOLD = "import sys; print(\'READY\', flush=True); sys.stdin.buffer.read()"', 1)
(HERE / "held_fixture.candidate.py").write_text(candidate, encoding="utf-8")
print("Prepared two isolated subjects; live test unchanged.")
