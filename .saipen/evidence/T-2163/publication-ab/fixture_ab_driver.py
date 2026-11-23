"""Wave F: A/B at the ONLY code the consolidation touched - fixture construction.

Arm A: original per-test construction (_build_source: surface copy + git init/add/commit).
Arm B: shared prepared fixture + per-test copytree (the XII consolidation).
The installer and every per-test publish path is identical in both arms and NOT
measured: the consolidation's delta is the construction site alone.
"""
import sys
import time
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "tools")
import test_t1613_publication_convergence as mod  # noqa: E402

ORIG_GIT = mod._Publisher._git


def _make_counter():
    counter = {"calls": 0}

    def git(instance, *args, **kwargs):
        counter["calls"] += 1
        return ORIG_GIT(instance, *args, **kwargs)

    return git, counter


def _bare_publisher(base):
    p = mod._Publisher.__new__(mod._Publisher)
    p.base = base
    p.source = base / "source"
    p.home = base / "user home"
    p.local = p.home / "AppData" / "Local"
    p._generation = 1
    return p


def measure(samples):
    out = {"samples": samples, "per_arm": {}}

    # ---- Arm A: original per-test _build_source ----
    git_a, counter_a = _make_counter()
    walls = []
    with patch.object(mod._Publisher, "_git", git_a):
        for _ in range(samples):
            base = Path(tempfile.mkdtemp(prefix="ab-a-"))
            p = _bare_publisher(base)
            started = time.monotonic()
            p._build_source()
            walls.append(time.monotonic() - started)
    out["per_arm"]["A_original_build_source"] = {
        "walls_s": [round(w, 4) for w in walls],
        "p50_s": round(sorted(walls)[len(walls) // 2], 4),
        "mean_s": round(sum(walls) / len(walls), 4),
        "git_processes_per_construction": counter_a["calls"] / samples,
    }

    # ---- Arm B: one preparation + per-test copytree ----
    prep = _bare_publisher(Path(tempfile.mkdtemp(prefix="ab-b-prep-")))
    prep_started = time.monotonic()
    prep._build_source()
    prep_s = time.monotonic() - prep_started

    git_b, counter_b = _make_counter()
    walls_b = []
    with patch.object(mod._Publisher, "_git", git_b):
        for _ in range(samples):
            base = Path(tempfile.mkdtemp(prefix="ab-b-"))
            target = base / "source"
            started = time.monotonic()
            mod.shutil.copytree(prep.source, target)
            walls_b.append(time.monotonic() - started)
    out["per_arm"]["B_shared_prep_then_copy"] = {
        "one_time_prep_s": round(prep_s, 4),
        "copy_walls_s": [round(w, 4) for w in walls_b],
        "copy_p50_s": round(sorted(walls_b)[len(walls_b) // 2], 4),
        "copy_mean_s": round(sum(walls_b) / len(walls_b), 4),
        "git_processes_per_construction": counter_b["calls"] / samples,
    }
    a = out["per_arm"]["A_original_build_source"]
    b = out["per_arm"]["B_shared_prep_then_copy"]
    out["delta_per_construction_s"] = round(a["mean_s"] - b["copy_mean_s"], 4)
    out["git_processes_per_construction_A_B"] = [
        a["git_processes_per_construction"],
        b["git_processes_per_construction"],
    ]
    return out


if __name__ == "__main__":
    print(json.dumps(measure(12), indent=2))
