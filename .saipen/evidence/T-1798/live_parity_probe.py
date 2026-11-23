"""Compare the real canonical launchers using one journaled disposable project."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
INSTALLED = Path(r"C:\Users\vac34\.agents\skills\saipen")
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.install_identity import install_fingerprint

temporary_base = Path(tempfile.gettempdir()).resolve()
temporary = tempfile.TemporaryDirectory(prefix="saipen-t1798-parity-", dir=temporary_base)
project = Path(temporary.name).resolve()
assert project.is_relative_to(temporary_base)
environment = {key: value for key, value in os.environ.items() if not key.startswith("SAIPEN_")}
environment.update({
    "PYTHONDONTWRITEBYTECODE": "1",
    "SAIPEN_CAPABILITY": "no-publish",
    "SAIPEN_LIBRARIAN": "off",
    "SAIPEN_GPU": "off",
    "SAIPEN_FORBID_HOST_SPAWN": "1",
    "SAIPEN_MACHINE_ROOT": str(project / "no-machine-runtime"),
    "SAIMAIL_WORKSPACE": str(project / "mail"),
})


def invoke(home, *arguments):
    launcher = home / "bin" / ("saipen.cmd" if os.name == "nt" else "saipen")
    result = subprocess.run(
        [str(launcher), *arguments, "--project-root", str(project), "--json"],
        cwd=project, env=environment, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload.get("ok"), payload
    return payload


try:
    source_fingerprint = install_fingerprint(ROOT)
    installed_fingerprint = install_fingerprint(INSTALLED)
    assert source_fingerprint == installed_fingerprint, (source_fingerprint, installed_fingerprint)
    relative = Path("tools/saipen_engine/regression_execution.py")
    assert (ROOT / relative).read_bytes() == (INSTALLED / relative).read_bytes()
    invoke(ROOT, "--agent", "install-probe", "init")
    invoke(ROOT, "rebind-home", str(INSTALLED))
    documents = ("STATE.md", "BOARD.md", "LOG.md")
    before = {name: hashlib.sha256((project / ".saipen" / name).read_bytes()).hexdigest()
              for name in documents}
    source = invoke(ROOT, "continue", "--dry-run")
    installed = invoke(INSTALLED, "continue", "--dry-run")
    semantic_keys = ("ok", "code", "action", "ticket", "reason")
    source_route = {key: source.get(key) for key in semantic_keys}
    installed_route = {key: installed.get(key) for key in semantic_keys}
    assert source_route == installed_route, (source_route, installed_route)
    after = {name: hashlib.sha256((project / ".saipen" / name).read_bytes()).hexdigest()
             for name in documents}
    assert before == after
    evidence = {"status": "PASS", "install_fingerprint": source_fingerprint,
                "request_clause_engine_bytes": "IDENTICAL", "source_route": source_route,
                "installed_route": installed_route, "dry_run_checkpoint_unchanged": True,
                "published": False}
    (ROOT / ".saipen/evidence/T-1798/live-parity.json").write_bytes(
        (json.dumps(evidence, indent=2) + "\n").encode("utf-8")
    )
    print(json.dumps(evidence))
finally:
    assert Path(temporary.name).resolve().is_relative_to(temporary_base)
    assert not Path(temporary.name).is_symlink()
    temporary.cleanup()
