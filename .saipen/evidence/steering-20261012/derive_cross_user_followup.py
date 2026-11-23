"""Keep the operator's full incident actionable on existing Work, without duplicates."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LAUNCHER = ROOT / "bin/saipen.cmd"
clauses = [
    ("requirement", "Determine from current evidence whether SMART_VAC_CLEANER AG3 and the prior SUNO_DOWNLOADER AG3 incidents share an actual root cause; do not assume the reports establish one."),
    ("requirement", "Verify current SAIPEN runtime resolution and independently prove project-root and lineage binding."),
    ("requirement", "Distinguish a runtime installed in another user's profile from each project's local canonical state."),
    ("requirement", "Identify the exact inaccessible V: ancestor and the exact filesystem operation required for continuation."),
    ("requirement", "Determine whether the reported BOARD validation failure follows runtime/access failure or is an independently reproduced defect."),
    ("requirement", "Verify T-199 existence, project identity, current lifecycle and authority before recommending any recovery action targeting it."),
    ("requirement", "Unavailable or inaccessible runtimes produce truthful structured results with a supported actionable recovery route where available."),
    ("invariant", "Preserve canonical state and prevent unsafe continuation; reported absence of modifications must be independently checked where evidence allows."),
    ("requirement", "Add regression coverage across multiple isolated real Windows identities, with doubles explicitly distinguished from live proof."),
    ("requirement", "SAITULS or Accounts Control Plane owner inspects actual AG3 launch identity and the account's permitted project roots."),
    ("requirement", "Host owner determines the narrow filesystem permissions required by the verified AG3 identity and project."),
    ("requirement", "Host owner checks runtime installation and executable resolution in AG3's actual security context."),
    ("invariant", "Preserve per-account credentials, profile isolation and unrelated private user data."),
    ("requirement", "Host owner provides a supported least-privilege runtime access route that permits authorized work."),
    ("invariant", "Do not broaden ACLs or impersonate another user without explicit authorization."),
    ("acceptance-criterion", "Reproduce and validate across two isolated standard-user accounts and independently bound project roots."),
    ("acceptance-criterion", "Authorized project and runtime access actually succeeds."),
    ("acceptance-criterion", "Unauthorized project or runtime access remains denied."),
    ("acceptance-criterion", "Runtime availability is reported truthfully in each actual identity and project binding."),
    ("acceptance-criterion", "Unrelated user-profile data never becomes accessible through the supported route."),
    ("acceptance-criterion", "Canonical records remain byte-identical on refused continuation or recovery."),
    ("acceptance-criterion", "Recovery never targets an unverified ticket or a ticket in an unverified project identity."),
    ("acceptance-criterion", "One blocked project does not stall independently admitted work in unrelated projects."),
    ("acceptance-criterion", "Existing account isolation remains intact after the correction."),
    ("acceptance-criterion", "Deliver the common root cause only if proven and identify the exact responsible project for every correction, with uncertainty and independent defects retained."),
    ("invariant", "Reuse existing incident Work where it covers the defect; do not open a duplicate generic Work."),
    ("invariant", "A clean BLOCKED diagnostic alone cannot close this incident or satisfy runtime-availability acceptance."),
    ("acceptance-criterion", "Success requires a real authorized AG3 continuation test under the verified intended identity; the SMART_VAC_CLEANER report names saiag_9fabb0d5 and T-195 BUILD, which remain unverified until freshly checked."),
]
principles = [
    ("requirement", "Safely enable the agent to perform authorized work using every applicable supported runtime, binding and recovery route; explanation of refusal alone is insufficient."),
    ("acceptance-criterion", "Keep the affected continuation incident open until working authorized continuation is proven; test available safe alternatives and name exact residual prerequisites honestly without weakening identity, isolation or canonical authority."),
]

outcomes = []
for receipt, rows in (("SRC-222", clauses), ("SRC-223", principles)):
    for number, (kind, text) in enumerate(rows, 1):
        argv = [str(LAUNCHER), "--json", "source", "req", receipt,
                f"R{number:03d}", kind, text]
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True,
                                encoding="utf-8", timeout=60, check=False)
        payload = json.loads(result.stdout)
        outcomes.append({"receipt": receipt, "clause": f"R{number:03d}",
                         "exit_code": result.returncode, "result": payload})
        if result.returncode or not payload.get("ok"):
            raise RuntimeError(json.dumps(outcomes[-1]))

output = Path(__file__).with_name("cross-user-derivation.json")
output.write_text(json.dumps({"new_work": 0, "primary_work": "T-1647",
                              "real_account_work": "T-1652", "outcomes": outcomes},
                             indent=2) + "\n", encoding="utf-8")
print(json.dumps({"SRC-222_clauses": len(clauses), "SRC-223_clauses": len(principles),
                  "new_work": 0, "receipt_outcomes": len(outcomes),
                  "live_AG3_success": "NOT_CLAIMED"}))
