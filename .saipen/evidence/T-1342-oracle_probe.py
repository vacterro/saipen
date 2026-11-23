"""VERIFY-ORACLE-01 behavioural probe: ONE oracle, run against two subjects.

Usage: python oracle_probe.py <subject-root>

<subject-root> is a tree whose tools/ holds the implementation under test (the
pre-fix installed snapshot, or the current repository). The fixtures are built
here and are identical for both subjects; only the imported implementation
varies. Prints one JSON object of observed verdicts. Nothing outside a temp
directory is written.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest.mock
from pathlib import Path

SUBJECT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(SUBJECT / "tools"))

import autoinject as A  # noqa: E402
import saipen_engine.runtime_bootstrap as RB  # noqa: E402
import saipen_engine.runtime_surface as RS  # noqa: E402

MINI = {
    "copy_trees": [
        {"src": "saipen/phases", "dst": "phases"},
        {"src": "tools", "dst": "tools"},
        {"src": "extensions/adapters", "dst": "extensions/adapters"},
    ],
    "files": [
        {"src": "saipen/MANIFEST.json", "required": True},
        {"src": "saipen/BOOT.md", "required": True},
        {"src": "VERSION", "required": True},
    ],
}


def authority(base: Path) -> Path:
    (base / "saipen" / "phases").mkdir(parents=True)
    (base / "saipen" / "MANIFEST.json").write_text(json.dumps(MINI), "utf-8")
    (base / "saipen" / "BOOT.md").write_text("# BOOT\n", "utf-8")
    (base / "saipen" / "phases" / "done.md").write_text("# DONE\n", "utf-8")
    (base / "VERSION").write_text("9.9.9\n", "utf-8")
    (base / "tools" / "saipen_engine").mkdir(parents=True)
    (base / "tools" / "saipen.py").write_text("# engine v1\n", "utf-8")
    (base / "tools" / "saipen_engine" / "board.py").write_text("# board v1\n", "utf-8")
    (base / "extensions" / "adapters").mkdir(parents=True)
    (base / "extensions" / "adapters" / "registry.json").write_text('{"adapters": []}', "utf-8")
    return base


def flatten(source: Path, target: Path) -> Path:
    shutil.copytree(source, target)
    for member in sorted((target / "saipen").iterdir()):
        member.replace(target / member.name)
    (target / "saipen").rmdir()
    cli = (target / "tools" / "saipen.py").resolve()
    (target / "bin").mkdir()
    (target / "bin" / "saipen").write_text(f'exec python "{cli}" "$@"\n', "utf-8")
    (target / "bin" / "saipen.cmd").write_text(f'python "{cli}" %*\r\n', "utf-8")
    return target


def stamp(home: Path, digest: str | None, head: str) -> None:
    (home / A.STAMP).write_text(
        json.dumps({"digest": digest, "source_head": head, "installed_at": "2026-09-15T00:00:00Z"}),
        "utf-8",
    )


verdicts: dict[str, object] = {"subject": str(SUBJECT)}
base = Path(tempfile.mkdtemp(prefix="saipen-oracle-"))
source = authority(base / "source")
head = "c" * 40

# P1: stamp + head current, executed engine stale -> must NOT be fresh.
home = flatten(source, base / ".opencode" / "skills" / "saipen")
stamp(home, RS.runtime_generation_identity(source), head)
(home / "tools" / "saipen.py").write_text("# stale engine\n", "utf-8")
with unittest.mock.patch.object(A, "HOME", source), \
        unittest.mock.patch.object(A, "TARGETS", [home]), \
        unittest.mock.patch.object(A, "last_inject_run", return_value=None):
    verdicts["P1_stale_engine_distribution_fresh"] = A.distribution_report(source_head=head)["fresh"]

# P2: a copied current stamp over stale bytes -> --check must exit 1.
out = io.StringIO()
with unittest.mock.patch.object(A, "HOME", source), \
        unittest.mock.patch.object(A, "TARGETS", [home]), \
        contextlib.redirect_stdout(out):
    verdicts["P2_copied_stamp_check_rc"] = A.main(["--check"])

# P3: extra installed module, valid marker -> prelaunch must be STALE.
installed = flatten(source, base / "extra" / "saipen")
(installed / RB.PROVENANCE_FILENAME).write_text(
    json.dumps(
        {
            "schema_version": 1,
            "adapter_id": "probe",
            "canonical_source_root": str(source),
            "installer_generation": RB.GENERATION,
            "runtime_fingerprint": RB.surface_fingerprint(source),
        }
    ),
    "utf-8",
)
(installed / "tools" / "saipen_engine" / "leftover.py").write_text("# stray\n", "utf-8")
registry = {"adapters": [{"id": "probe", "install": {"skill": str(installed)}}]}
with unittest.mock.patch.object(RB, "_registry", return_value=registry):
    report = RB.prelaunch("probe", skill_root=source, resync=False)
verdicts["P3_extra_module_prelaunch_code"] = report["code"]

# P4: an instruction block naming a CURRENT published snapshot's protocol dir.
snapshot = base / "scheduled-source"
shutil.copytree(source, snapshot)
with unittest.mock.patch.object(A, "HOME", source):
    verdicts["P4_snapshot_protocol_dir_is_real_home"] = A._names_a_real_home(
        str(snapshot / "saipen")
    )

# P5: a junction as a declared tree root -> identity must be UNKNOWN.
if os.name == "nt":
    import _winapi

    junction_root = base / "junction"
    shutil.copytree(source, junction_root)
    real = junction_root / "adapters-real"
    shutil.move(str(junction_root / "extensions" / "adapters"), str(real))
    _winapi.CreateJunction(str(real), str(junction_root / "extensions" / "adapters"))
    verdicts["P5_junction_tree_identity_is_none"] = (
        RS.runtime_generation_identity(junction_root) is None
    )

# P6: NUL-bearing CRLF vs LF payloads -> identities must differ.
one = base / "nul-one"
two = base / "nul-two"
shutil.copytree(source, one)
shutil.copytree(source, two)
(one / "tools" / "record.dat").write_bytes(b"structured\x00record\r\n")
(two / "tools" / "record.dat").write_bytes(b"structured\x00record\n")
verdicts["P6_nul_payloads_differ"] = (
    RS.runtime_generation_identity(one) != RS.runtime_generation_identity(two)
)

# P7: two declared names landing on one installed path -> UNKNOWN.
collide = base / "collide"
shutil.copytree(source, collide)
(collide / "saipen" / "VERSION").write_text("0.0.0\n", "utf-8")
manifest = dict(MINI, files=[*MINI["files"], {"src": "saipen/VERSION", "required": True}])
(collide / "saipen" / "MANIFEST.json").write_text(json.dumps(manifest), "utf-8")
verdicts["P7_landing_collision_identity_is_none"] = (
    RS.runtime_generation_identity(collide) is None
)

print(json.dumps(verdicts, indent=2))
