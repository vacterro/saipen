"""Prepare the repository oracle in evidence while the live tree is frozen."""
from pathlib import Path

evidence = Path(__file__).resolve().parent
source = (evidence / "oracle.py").read_text(encoding="utf-8")
source = source.replace("import io\n", "import io\nimport json\n")
source = source.replace("import sys\n", "import sys\nimport subprocess\n")
source = source.replace("ROOT = Path(sys.argv.pop(1)).resolve()",
                        "ROOT = Path(__file__).resolve().parent.parent")
addition = '''    def test_the_cli_exposes_the_canonical_repair_action_without_starting_a_host(self):
        self.choose("strict")
        child = """
import sys
from unittest import mock
import tools.saipen as cli
from saipen_engine import host_launch, runtime_bootstrap
report = {"ok": False, "code": "T1686_UNPROVEN", "detail": "unproven runtime"}
with mock.patch.object(runtime_bootstrap, "prelaunch", return_value=report) as proof, \\
        mock.patch.object(host_launch.shutil, "which") as locate, \\
        mock.patch.object(host_launch.subprocess, "run") as spawn:
    code = cli.main(["--json", "--project-root", sys.argv[1], "--agent", "oracle-seat",
                     "launch", "claude"])
    proof.assert_called_once_with("claude", resync=True)
    locate.assert_not_called()
    spawn.assert_not_called()
raise SystemExit(code)
"""
        completed = subprocess.run(
            [sys.executable, "-B", "-c", child, str(self.project)], cwd=ROOT,
            env=hermetic.hermetic_env(HOME=str(self.home), USERPROFILE=str(self.home),
                                      HOMEDRIVE="", HOMEPATH="", PYTHONUTF8="1"),
            capture_output=True, encoding="utf-8", timeout=30,
        )
        self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
        reply = json.loads(completed.stdout)
        self.assertFalse(reply["ok"])
        self.assertEqual(reply["code"], "HOST_LAUNCH_REFUSED")
        self.assertEqual(reply.get("operator_action"), taxonomy.REPAIR)
        self.assertIn("T1686_UNPROVEN", reply["detail"])


'''
anchor = '\n\nif __name__ == "__main__":'
if source.count(anchor) != 1:
    raise ValueError("oracle tail moved")
source = source.replace(anchor, "\n\n" + addition + 'if __name__ == "__main__":')
target = evidence / "candidate" / "tools" / "test_t1686_strict_launch.py"
target.parent.mkdir(parents=True, exist_ok=True)
if target.exists():
    raise ValueError("repository candidate oracle already exists")
target.write_text(source, encoding="utf-8")
print(target)
