import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))
import run_scenarios as scenarios

before = OUT / "before"
for relative in (
    ".gitignore", "bootstrap/install_ownership.py", "tools/validate.py",
    "tools/run_scenarios.py",
):
    target = before / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes((ROOT / relative).read_bytes())

home = OUT / "injector-home-before"
home.mkdir(exist_ok=True)
bash = scenarios.find_bash()
stream = io.StringIO()
with contextlib.redirect_stdout(stream):
    problem = scenarios.run_injector_probe(
        "bootstrap/inject.sh",
        [bash, str(ROOT / "bootstrap/inject.sh")],
        [bash, str(ROOT / "bootstrap/uninstall.sh")],
        scenarios.bash_env(bash, home), home,
    )
destination = home / ".claude/skills/saipen"
leftovers = sorted(
    str(path.relative_to(destination)) for path in destination.rglob("*")
    if path.is_file()
)
result = {"problem": problem, "leftover_files": leftovers, "output": stream.getvalue()}
(OUT / "install-before.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))

locale_audit = []
for path in sorted((ROOT / ".saipen/saitranslate/kitchen").glob("*/README_*.md")):
    relative = path.relative_to(ROOT).as_posix()
    old = subprocess.run(
        ["git", "show", "914ea79a:" + relative], cwd=ROOT,
        capture_output=True, check=True,
    ).stdout.decode("utf-8-sig")
    current = path.read_text(encoding="utf-8-sig")
    import re
    normalize = lambda text: re.sub(r"\*\*v[0-9.]+\*\*", "**VERSION**", text)
    locale_audit.append({"path": relative, "only_version_changed": normalize(old) == normalize(current)})
(OUT / "locale-audit.json").write_text(json.dumps(locale_audit, indent=2), encoding="utf-8")
print(json.dumps({"locale_count": len(locale_audit), "non_version_deltas": [item for item in locale_audit if not item["only_version_changed"]]}))
