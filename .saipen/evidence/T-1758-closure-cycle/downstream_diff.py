"""T-1758 downstream diff: closure-evidence verdicts before and after, on copies.

Never touches a real project. For each listed project, copies `.saipen/`
(without cache/ and kitchen/) into a work directory, then runs the validator of
two engine copies at foreign paths -- BEFORE (the live tree with the pre-fix
log.py) and AFTER (the live tree as it is) -- with `--project-root <copy>
--gate core --no-receipt`, and records every FAIL line with its counts masked.

Usage (from the repository root):
    python -B .saipen/evidence/T-1758-closure-cycle/downstream_diff.py <workdir>
Writes <workdir>/diff.json and prints a summary.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CODE = REPO.parents[1]
HERE = Path(__file__).resolve().parent
PROJECTS = [
    "_AI_STUFF_AGENTIC/_SAICONT", "_AI_STUFF_AGENTIC/_SAIPAL", "_AI_STUFF_AGENTIC/_SAIRELAY",
    "_AI_STUFF_AGENTIC/_SAITALK", "_AI_STUFF_AGENTIC/_SAIWORK2", "_AI_STUFF_AGENTIC/__TERMISAI",
    "_ANDROID/ProBlipAndroid", "_HTML/_SAI_WEBSITE", "_PLUG_SCRIPT/_FREEBUFF_SAI",
    "_PY/_9router_extra", "_PY/_AUDAPACK_RECOVERY_20261010", "_PY/_PROBLIP", "_PY/_SAIMASTER",
    "_PY/_SAIPENVIEW", "_PY/_SAIPLAN", "_PY/_SMART_VAC_CLEANER",
    "_PY/_SMART_VAC_DUPLICATE_REMOVER", "_PY/_SMART_VAC_MEDIA_COMPRESSOR",
    "_PY/_VACZEN_CALENDAR", "_PY/_VacWPlayer", "_TAMPERMONKEY/_SUNO_DOWNLOADER",
    "__MAIN__/ProTrail", "__MAIN__/_SAICODE", "_AI_STUFF_AGENTIC/__SAIMAIL__", "_PY/_LIMISAW",
]
TREES = ("tools", "saipen", "extensions", "bootstrap", "tests")
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".ruff_cache")


def engine_copy(target: Path, *, log_py: Path | None) -> Path:
    target.mkdir(parents=True, exist_ok=True)
    for name in TREES:
        if (REPO / name).is_dir():
            shutil.copytree(REPO / name, target / name, ignore=IGNORE, dirs_exist_ok=True)
    for item in REPO.iterdir():
        if item.is_file():
            shutil.copy2(item, target / item.name)
    if log_py is not None:
        shutil.copy2(log_py, target / "tools" / "saipen_engine" / "log.py")
    return target


def project_copy(source: Path, target: Path) -> Path:
    memory = source / ".saipen"
    shutil.copytree(
        memory, target / ".saipen", ignore=shutil.ignore_patterns("cache", "kitchen", "locks")
    )
    return target


def fails(engine: Path, project: Path) -> list[str]:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
    env["PYTHONUTF8"] = "1"
    env.pop("CLAUDE_CONFIG_DIR", None)
    proc = subprocess.run(
        [sys.executable, "-B", str(engine / "tools" / "validate.py"), "--project-root",
         str(project), "--gate", "core", "--no-receipt"],
        capture_output=True, env=env, cwd=str(project), timeout=1200, check=False,
    )
    text = proc.stdout.decode("utf-8", "replace")
    lines = [line for line in text.splitlines() if line.startswith("FAIL")]
    masked = sorted({re.sub(r"\b[0-9a-f]{12,64}\b", "<hex>", re.sub(r"\d+", "N", ln)) for ln in lines})
    return masked


def main() -> int:
    work = Path(sys.argv[1]).resolve()
    work.mkdir(parents=True, exist_ok=True)
    before_log = HERE / "before" / "log.py"
    before = engine_copy(work / "engine-before", log_py=before_log)
    after = engine_copy(work / "engine-after", log_py=None)
    report: dict[str, dict] = {}
    for rel in PROJECTS:
        source = CODE / rel
        if not (source / ".saipen" / "STATE.md").is_file():
            report[rel] = {"skipped": "no .saipen"}
            continue
        copy = project_copy(source, work / "projects" / rel.replace("/", "__"))
        old, new = fails(before, copy), fails(after, copy)
        report[rel] = {
            "before": len(old), "after": len(new),
            "removed": [ln for ln in old if ln not in new],
            "added": [ln for ln in new if ln not in old],
        }
        print(f"{rel}: before {len(old)} after {len(new)} "
              f"removed {len(report[rel]['removed'])} added {len(report[rel]['added'])}", flush=True)
    (work / "diff.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    added = sum(len(v.get("added", [])) for v in report.values())
    removed = sum(len(v.get("removed", [])) for v in report.values())
    print(f"TOTAL removed {removed} added {added}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
