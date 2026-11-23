import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
records = {}
for label, command in (
    ("default", ["git", "diff", "--check"]),
    ("crlf", ["git", "-c", "core.whitespace=cr-at-eol", "diff", "--check"]),
):
    run = subprocess.run(command, cwd=ROOT, capture_output=True)
    (HERE / f"whitespace-{label}.stdout.txt").write_bytes(run.stdout)
    (HERE / f"whitespace-{label}.stderr.txt").write_bytes(run.stderr)
    headers = [line for line in run.stdout.decode("utf-8", "replace").splitlines()
               if not line.startswith("+")]
    records[label] = {"command": command, "exit_code": run.returncode,
                      "finding_count": len(headers), "sample": headers[:8]}

# Same checker must accept canonical CRLF and reject a real trailing space.
with tempfile.TemporaryDirectory(prefix="saipen-whitespace-control-") as temp:
    root = Path(temp)
    for command in (["git", "init", "-q"], ["git", "config", "core.autocrlf", "false"]):
        subprocess.run(command, cwd=root, check=True, capture_output=True)
    (root / ".gitattributes").write_bytes(b"memory.md -text\n")
    memory = root / "memory.md"
    memory.write_bytes(b"before\r\n")
    subprocess.run(["git", "add", "--", ".gitattributes", "memory.md"],
                   cwd=root, check=True, capture_output=True)
    controls = {}
    for name, content in (("valid_crlf", b"after\r\n"),
                          ("trailing_space", b"after \r\n")):
        memory.write_bytes(content)
        result = subprocess.run(["git", "-c", "core.whitespace=cr-at-eol", "diff", "--check"],
                                cwd=root, capture_output=True)
        controls[name] = {"exit_code": result.returncode,
                          "stdout": result.stdout.decode("utf-8", "replace")}
    records["controls"] = controls
(HERE / "whitespace.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
print(json.dumps(records, indent=2))
