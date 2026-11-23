import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "tools"))
from saipen_engine import suite_record

with tempfile.TemporaryDirectory(prefix="saipen-nested-subject-") as directory:
    root = Path(directory)
    (root / ".gitignore").write_text("/vrv/\n", encoding="utf-8")
    (root / "vrv").mkdir()
    production = root / "vrv" / "DllBase.cpp"
    production.write_text("before", encoding="utf-8")
    for args in (["init", "-q"], ["add", "."], ["commit", "-qm", "fixture"]):
        subprocess.run(
            ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid", *args],
            cwd=root, capture_output=True, check=True,
        )
    first = suite_record.subject(root)
    production.write_text("after", encoding="utf-8")
    second = suite_record.subject(root)
    print("IGNORED_SUITE_SUBJECT_UNCHANGED=" + str(first == second))
