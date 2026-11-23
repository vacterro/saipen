"""Run the current recovery oracle unchanged against committed pre-fix code."""
import pathlib
import subprocess
import sys
import tempfile
import zipfile

repo = pathlib.Path(__file__).resolve().parents[4]
output = pathlib.Path(__file__).with_name("T-1609-red-control.txt")
with tempfile.TemporaryDirectory(prefix="saipen-t1609-red-") as temp:
    root = pathlib.Path(temp)
    archive = root / "subject.zip"
    subprocess.run(["git", "archive", "HEAD", "--format=zip", "-o", str(archive)],
                   cwd=repo, check=True, capture_output=True)
    subject = root / "subject"
    with zipfile.ZipFile(archive) as stream:
        stream.extractall(subject)
    oracle = repo / "tools/test_t1609_unproven_done_recovery.py"
    (subject / "tools" / oracle.name).write_bytes(oracle.read_bytes())
    run = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover",
                          "-s", "tools", "-p", oracle.name, "-v"], cwd=subject,
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    output.write_text(run.stdout + run.stderr, encoding="utf-8")
    print(f"unchanged oracle/pre-fix HEAD: rc={run.returncode}; {output}")
    if run.returncode == 0:
        raise SystemExit("red control unexpectedly passed")
