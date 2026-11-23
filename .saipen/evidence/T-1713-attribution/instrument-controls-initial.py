"""Prove the unchanged forensic verifier accepts good and rejects altered operands."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.core_unit import tree_fingerprint
from saipen_engine.state import parse_state


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    stage = sys.argv[1]
    state = parse_state((ROOT / ".saipen/STATE.md").read_text(encoding="utf-8"))
    if state.get("task") != "T-1713" or state.get("phase") != stage.upper():
        raise RuntimeError("T-1713 does not own the requested control phase")
    output = HERE / (stage + "-instrument-controls.json")
    if output.exists():
        raise RuntimeError("existing instrument evidence is immutable")
    original = HERE / "verify-attribution.py"
    spec = importlib.util.spec_from_file_location("t1713_instrument_controls", original)
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    baseline = tree_fingerprint(ROOT)
    canonical = {name: sha((ROOT / ".saipen" / name).read_bytes())
                 for name in ("STATE.md", "BOARD.md", "LOG.md")}
    index = subprocess.run(["git", "ls-files", "--stage"], cwd=ROOT,
                           capture_output=True, check=True).stdout
    controls = []
    with tempfile.TemporaryDirectory(prefix="t1713-instrument-") as temporary:
        base = Path(temporary)
        for label, expected in (("good", None),
                                ("changed_historical_subject", "historical subject identity moved"),
                                ("false_sealed_hash", "an inspected sealed segment changed")):
            prepared = base / label / "prepared"
            shutil.copytree(verifier.PREPARED, prepared)
            evidence = base / label / "evidence"
            evidence.mkdir()
            shutil.copyfile(HERE / "MATRIX.md", evidence / "MATRIX.md")
            if label == "changed_historical_subject":
                subject = prepared / "historical-subjects/manifest-8f91d779.py"
                subject.write_bytes(subject.read_bytes() + b"\n# deliberately changed control\n")
            if label == "false_sealed_hash":
                carrier = prepared / "attribution-provenance.json"
                data = json.loads(carrier.read_text(encoding="utf-8"))
                first = next(iter(data["sealed_log_hashes"]))
                data["sealed_log_hashes"][first] = "0" * 64
                carrier.write_text(json.dumps(data), encoding="utf-8")
            verifier.PREPARED = prepared
            verifier.HERE = evidence
            sys.argv = [str(original), stage]
            try:
                verifier.main()
            except RuntimeError as exc:
                if expected is None or expected not in str(exc):
                    raise
                if (evidence / (stage + "-attribution.json")).exists():
                    raise RuntimeError("bad instrument input produced a success artifact")
                controls.append({"input": label, "accepted": False,
                                 "exception": type(exc).__name__, "detail": str(exc)})
            else:
                if expected is not None:
                    raise RuntimeError("changed forensic operand was accepted: " + label)
                result = json.loads((evidence / (stage + "-attribution.json")).read_text(encoding="utf-8"))
                if result.get("ok") is not True:
                    raise RuntimeError("known-good forensic input did not pass")
                controls.append({"input": label, "accepted": True,
                                 "historical_reproductions": len(result["historical_reproductions"])})
    if tree_fingerprint(ROOT) != baseline:
        raise RuntimeError("instrument controls changed the live subject")
    if canonical != {name: sha((ROOT / ".saipen" / name).read_bytes()) for name in canonical}:
        raise RuntimeError("instrument controls changed canonical memory")
    if subprocess.run(["git", "ls-files", "--stage"], cwd=ROOT,
                      capture_output=True, check=True).stdout != index:
        raise RuntimeError("instrument controls changed the Git index")
    result = {"ok": True, "stage": stage, "verifier_sha256": sha(original.read_bytes()),
              "matrix_sha256": sha((HERE / "MATRIX.md").read_bytes()), "controls": controls,
              "tree_fingerprint": baseline, "canonical_unchanged": True, "index_unchanged": True,
              "limits": "Identical verifier code; only disposable copies of its forensic operands changed. "
                        "No claim of a historical complete-installation boot or unavailable AG3 token."}
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "stage": stage, "controls": controls, "record": str(output)}))


if __name__ == "__main__":
    main()
