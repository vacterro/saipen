"""Execute the original forensic verifier in a fresh phase evidence location."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> None:
    stage = sys.argv[1]
    if stage not in {"verify", "review"}:
        raise ValueError("expected verify or review")
    output = HERE / (stage + "-attribution-current.json")
    if output.exists():
        raise RuntimeError("existing current-phase evidence is immutable")
    script = HERE / "verify-attribution.py"
    spec = importlib.util.spec_from_file_location("t1713_fresh_phase", script)
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    identity = hashlib.sha256(script.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="t1713-phase-") as temporary:
        evidence = Path(temporary)
        shutil.copyfile(HERE / "MATRIX.md", evidence / "MATRIX.md")
        verifier.HERE = evidence
        sys.argv = [str(script), stage]
        verifier.main()
        result = json.loads((evidence / (stage + "-attribution.json")).read_text(encoding="utf-8"))
    if identity != hashlib.sha256(script.read_bytes()).hexdigest():
        raise RuntimeError("forensic verifier changed during fresh-phase execution")
    result["executed_verifier_sha256"] = identity
    result["phase_recorder_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result["command"] = [sys.executable, "-B", str(Path(__file__).resolve()), stage]
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": result["ok"], "stage": stage, "record": str(output),
                      "history_events": result["parsed_events"], "verifier_sha256": identity}))


if __name__ == "__main__":
    main()
