"""T-1746: the SRC-240 route on a disposable copy of the real downstream bytes.

usage: python wintage_copy_probe.py <engine_tools_dir> <copy_root> <real_root> <step>

step: plan | ship | verdict

Reads and writes ONLY <copy_root>. <real_root> is named so the engine refuses a
call that resolved it (FORBID_SAIPEN_PROJECT_WRITE). The session capability is
`no-publish`, the capability the mission authorizes for the local closure.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> int:
    tools, copy_root, real_root, step = sys.argv[1:5]
    for key in [key for key in os.environ if key.startswith("SAIPEN")]:
        del os.environ[key]
    os.environ["SAIPEN_CAPABILITY"] = "no-publish"
    os.environ["FORBID_SAIPEN_PROJECT_WRITE"] = real_root
    sys.path.insert(0, tools)
    root = Path(copy_root).resolve()
    if root == Path(real_root).resolve():
        raise SystemExit("refusing to run on the real project")
    os.chdir(root)

    from saipen_engine import crew, release

    if step == "plan":
        plan = crew.crew_plan(root, current_capability="no-publish")
        stages = [
            {key: stage.get(key) for key in ("stage", "state", "reason")}
            for stage in plan.get("stages", [])
        ]
        out = {
            "ok": plan.get("ok"),
            "code": plan.get("code"),
            "next_action": plan.get("next_action") or plan.get("action"),
            "stages": stages,
        }
        context = crew.crew_release_context(root)
        out["release_context"] = {
            "ok": context.get("ok"),
            "detail": context.get("detail"),
            "crew_epoch": context.get("crew_epoch"),
            "ticket_id": context.get("ticket_id"),
            "scope_paths": sorted(context.get("crew_defer_scope") or {}),
        }
        print(json.dumps(out, indent=2, default=str))
        return 0
    if step == "ship":
        try:
            plan = release.plan_release(root, "ship", current_capability="no-publish")
        except release.ReleaseRefusal as exc:
            print(json.dumps({"planned": False, "code": exc.code, "detail": exc.detail}, indent=2))
            return 1
        summary = {
            "planned": True,
            "op_id": plan.op_id,
            "mode": plan.mode,
            "version": plan.version,
            "tag": plan.tag,
            "ticket_id": plan.ticket_id,
            "crew_epoch": plan.crew_epoch,
            "scope_paths": list(plan.scope_paths),
        }
        result = release.execute_release(root, plan)
        summary["result"] = result
        print(json.dumps(summary, indent=2, default=str))
        return 0 if result.get("ok") else 1
    if step.startswith("recover:"):
        result = release.recover_release_op(root, step.split(":", 1)[1])
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("ok") else 1
    if step == "verdict":
        snapshot = crew.crew_snapshot(root, current_capability="no-publish")
        epoch = snapshot.epoch
        verdict = release.release_verdict(root, crew_epoch=epoch.op_id if epoch else None)
        current = crew._release_current(snapshot)
        print(
            json.dumps(
                {
                    "state_mode": snapshot.state.get("mode"),
                    "epoch": epoch.op_id if epoch else None,
                    "epoch_ticket": epoch.ticket if epoch else None,
                    "verdict": verdict,
                    "release_current": list(current),
                },
                indent=2,
                default=str,
            )
        )
        return 0
    raise SystemExit(f"unknown step {step!r}")


if __name__ == "__main__":
    sys.exit(main())
