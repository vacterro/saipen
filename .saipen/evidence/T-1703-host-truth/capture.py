"""Read-only B01 evidence: registry claims, installed facts, and unspent probes."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
PREFIX = sys.argv[1]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import admission, host_integration

registry_path = ROOT / "extensions/adapters/registry.json"
registry = json.loads(registry_path.read_bytes())
process = subprocess.run([str(ROOT / "bin/saipen.cmd"), "host", "doctor", "--json"],
                         cwd=ROOT, capture_output=True, timeout=120)
doctor = json.loads(process.stdout)
assert doctor["code"] == "HOST_DOCTOR" and doctor["source"]["proven"]
assert process.returncode == (0 if doctor["ok"] else 1)
assert Path(doctor["source"]["canonical"]).resolve() == ROOT.resolve()
(OUT / (PREFIX + "-doctor.json")).write_bytes(process.stdout)
assert {row["id"] for row in doctor["hosts"]} == {row["id"] for row in registry["adapters"]}
rows = []
for adapter in registry["adapters"]:
    contract = host_integration.capability_contract(adapter)
    assert not host_integration.contract_gaps(contract)
    for installed in (row for row in doctor["hosts"] if row["id"] == adapter["id"]):
        hook = installed["facts"]["hook"]
        strength = admission.effective_strength(adapter["id"], hook_path=hook.get("path"))
        assert strength["effective"] != "BLOCKING", "no real host probe was spent in this observation"
        rows.append({
            "host": adapter["id"], "profile": installed.get("profile"),
            "declared": {"TOOL_BLOCK": contract["tool_interception"],
                         "ADMISSION": contract["admission_enforcement"],
                         "QUESTION": adapter["question_enforcement"],
                         "FINAL_RESPONSE": contract["response_enforcement"]},
            "installed": {"state": installed["state"], "runtime": installed["runtime"],
                          "hook": installed["hook"], "hook_path": hook.get("path"),
                          "runtime_facts": installed["facts"]["runtime"]},
            "owner_projections": {"tool_strength_without_positive_probe": strength,
                                  "admission": installed["admission"],
                                  "final_response": installed["response_enforcement"]},
            "actual_host_boundary_probes": {name: "NOT_PROBED" for name in
                                            ("TOOL_BLOCK", "ADMISSION", "QUESTION", "FINAL_RESPONSE")},
            "retained_prior_health": installed["last_health"],
            "health_limit": "Prior prompt health is not a new tool/question/final-response execution probe.",
            "action": installed["action"],
        })
for host in ("freebuff", "antigravity"):
    row = next(item for item in rows if item["host"] == host)
    assert row["declared"]["TOOL_BLOCK"] == "ADVISORY"
    assert row["declared"]["ADMISSION"] == "ADVISORY"
evidence = {"observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "source": doctor["source"], "registry_sha256": hashlib.sha256(registry_path.read_bytes()).hexdigest(),
            "doctor_exit_code": process.returncode, "doctor_ok": doctor["ok"],
            "broken_hosts": doctor["broken"], "machine_runtime": doctor["machine_runtime"],
            "authority_running": doctor["authority"]["running"], "path_launcher": doctor["path_launcher"],
            "rows": rows, "live_writes": 0, "host_processes_started": 0,
            "boundary": "Read-only source evidence; installed/declared is not a proven live host interception."}
(OUT / (PREFIX + "-matrix.json")).write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
lines = ["# Current host capability truth — B01", "",
         "Registry declarations, installed currentness and actual execution probes are separate.",
         "All four live boundary probes are NOT_PROBED; no host was started or repaired.",
         "The effective-strength owner receives no fabricated positive guard/health evidence.", "",
         "| Host/profile | TOOL_BLOCK | ADMISSION | QUESTION | FINAL_RESPONSE | Runtime / hook | Tool owner without probe |", 
         "| --- | --- | --- | --- | --- | --- | --- |"]
for row in rows:
    d, i = row["declared"], row["installed"]
    name = row["host"] + (" / " + row["profile"] if row["profile"] else "")
    lines.append("| " + " | ".join((name, d["TOOL_BLOCK"], d["ADMISSION"], d["QUESTION"],
        d["FINAL_RESPONSE"], i["runtime"] + " / " + i["hook"],
        row["owner_projections"]["tool_strength_without_positive_probe"]["effective"])) + " |")
lines.extend(["", "Native doctor exit: " + str(process.returncode) + "; broken hosts: " +
              ", ".join(doctor["broken"]) + ". These are retained observed conditions.",
              "Machine runtime: " + doctor["machine_runtime"]["code"] + "; authority running: " +
              str(doctor["authority"]["running"]) + ".", "",
              "A source checkout proves this report's code identity, not the loaded generation of another host.",
              "Historical prompt health and an owner projection of MECHANICAL do not prove a live QUESTION or FINAL_RESPONSE probe.",
              "ADVISORY is the registry ceiling for FreeBuff/Antigravity; no blocking transport is invented.",
              "A same-user hook/broker is not an NTFS isolation boundary. C01-C06 remain distinct operator-gated work."])
(OUT / (PREFIX + "-matrix.md")).write_text("\n".join(lines) + "\n", encoding="utf-8")
print(json.dumps({"registered_hosts": len(registry["adapters"]), "profile_rows": len(rows),
                  "doctor_exit_code": process.returncode, "broken": doctor["broken"],
                  "machine_runtime": doctor["machine_runtime"]["code"], "live_writes": 0,
                  "actual_boundary_probes": "NOT_PROBED"}))
