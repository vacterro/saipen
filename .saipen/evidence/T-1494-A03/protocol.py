"""Record the existing canonical launcher; restrict this session to no-publish."""
import json
import os
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]


def invoke(label, arguments):
    env = {**os.environ, "SAIPEN_CAPABILITY": "no-publish", "PYTHONIOENCODING": "utf-8"}
    command = [str(ROOT / "bin/saipen.cmd"), *arguments, "--json"]
    result = subprocess.run(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                            capture_output=True, timeout=300,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    (OUT / (label + "-stdout.txt")).write_bytes(result.stdout)
    (OUT / (label + "-stderr.txt")).write_bytes(result.stderr)
    payload = json.loads(result.stdout.decode("utf-8-sig"))
    record = {"command": command, "exit_code": result.returncode,
              "session_capability": "no-publish", "result": payload}
    op_id = payload.get("op_id")
    if payload.get("ok") and op_id:
        manifest = ROOT / ".saipen/recovery/settled" / op_id / "operation.json"
        journal = json.loads(manifest.read_text(encoding="utf-8"))
        record["committed_operation"] = {
            "path": str(manifest.relative_to(ROOT)), "status": journal["status"],
            "operation": journal["operation"], "progress_index": journal["progress_index"],
            "targets": [{"path": target["path"], "applied": target["applied"]}
                        for target in journal["targets"]],
        }
        assert journal["status"] == "COMMITTED", record
        assert all(target["applied"] for target in journal["targets"]), record
    (OUT / (label + ".json")).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=True, indent=2), flush=True)
    if result.returncode or not payload.get("ok"):
        raise SystemExit(result.returncode or 1)
    return payload


if __name__ == "__main__":
    invoke(sys.argv[1], sys.argv[2:])
