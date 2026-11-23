"""saiwiki FORCE-FRESH page refresh (W-053).

W-052 was prepared at HEAD b152e6de / tree b580f1f6 over v8.1.0. Since then the
pending v8.2.0 release batch moved the canonical version surfaces in the
working tree (VERSION, README badge, CHANGELOG top entry dated 2026-11-03) and
one commit (66ef622a, T-1950) landed past the binding, so the package no longer
describes the tree it claims. This pass re-reads all nine maintained pages
against the CURRENT triple and applies the drift the canonical owners actually
show.

Every edit is an exact, single-match replacement with an assertion: an anchor
that matches nothing, or matches twice, is a hard failure -- a producer never
guesses. Re-running the script is a no-op (see `_replace`).

Owners mirrored by each correction:

  * Home badge + Key features heading + new v8.2.0 bullet: the CHANGELOG's top
    entry is 8.2.0 (T-2011, host acceptance tells execution from dispatch) and
    the README badge/VERSION in the current tree read 8.2.0; the wiki still
    said v8.1.0.
  * Home inventory: re-measured on today's bytes -- 617 `tools/test_*.py`
    modules declaring 8962 test methods, and the mutation-control harness
    declares 276 full-sweep controls. W-052 carried 572 / 8311 / 276.
  * _Footer: version string follows the same canonical surfaces.
  * SubSaipen: this producer's own status row, rebound to W-053.

The script touches only `.saipen/extensions/subs/saiwiki/kitchen/wiki/`, this
producer's own payload. It never writes the main tree and performs no
integration, commit, tag, push or remote write.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
WIKI = ROOT / ".saipen" / "extensions" / "subs" / "saiwiki" / "kitchen" / "wiki"
CORPUS = ROOT / "tests" / "conformance_cases.jsonl"

APPLIED: list[str] = []
ALREADY: list[str] = []

def _replace(page: str, old: str, new: str, label: str, *, gone: str | None = None) -> None:
    """Exact single-match replacement, idempotent for insertions and deletions.

    A deletion edit (`new` empty) cannot use "the result is present" as its
    already-applied test, so a deletion names `gone`: the token the removed row
    carried. Applied means the anchor is there exactly once; already-applied
    means the anchor is gone AND that token is nowhere in the page.
    """
    path = WIKI / page
    text = path.read_text(encoding="utf-8")
    if new:
        if new in text:
            ALREADY.append(label)
            return
    elif old not in text:
        if gone is None:
            raise AssertionError(f"{label}: a deletion edit needs a `gone` postcondition")
        if gone in text:
            raise AssertionError(
                f"{label}: anchor gone but the removed row's token {gone!r} is still present"
            )
        ALREADY.append(label)
        return
    if not old:
        raise AssertionError(f"{label}: empty anchor")
    hits = text.count(old)
    if hits != 1:
        raise AssertionError(f"{label}: anchor matched {hits} times, expected 1")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="")
    APPLIED.append(label)

def measure() -> dict[str, object]:
    """The inventory truth, measured on the bytes this package binds to."""
    import sys

    sys.path.insert(0, str(ROOT / "tools"))
    import audit_checks  # noqa: PLC0415

    modules = sorted(ROOT.glob("tools/test_*.py"))
    methods = 0
    for module in modules:
        for line in module.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.lstrip().startswith("def test_"):
                methods += 1
    return {
        "modules": len(modules),
        "methods": methods,
        "controls": audit_checks.FULL_CASE_COUNT,
    }

def refresh_scenarios() -> str:
    """Rebuild the mirror marker and every mirrored row from the canonical corpus."""
    path = WIKI / "Scenarios.md"
    text = path.read_text(encoding="utf-8")
    cases = {
        int(json.loads(line)["id"]): json.loads(line)["setup"]
        for line in CORPUS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    top = max(cases)
    digest = hashlib.sha256(
        "\n".join(f"{key}|{cases[key]}" for key in sorted(cases)).encode("utf-8")
    ).hexdigest()[:16]

    fixed = 0
    lines = text.split("\n")
    for index, line in enumerate(lines):
        stripped = line.lstrip("| ")
        if not stripped[:1].isdigit():
            continue
        number, _, rest = stripped.partition(" | ")
        if not number.isdigit():
            continue
        case_id = int(number)
        if case_id not in cases:
            continue
        cells = rest.rstrip("|").split(" | ")
        if not cells:
            continue
        if cells[0] != cases[case_id]:
            cells[0] = cases[case_id]
            lines[index] = "| " + number + " | " + " | ".join(cells) + " |"
            fixed += 1
    text = "\n".join(lines)

    marker_new = f"<!-- mirrors: CONFORMANCE.md rows 1-{top} sha256:{digest} -->"
    current = [line for line in text.split("\n") if line.startswith("<!-- mirrors: ")]
    if len(current) != 1:
        raise AssertionError(f"Scenarios: {len(current)} mirror markers, expected 1")
    if current[0] != marker_new:
        text = text.replace(current[0], marker_new, 1)
    path.write_text(text, encoding="utf-8", newline="")
    return f"rows corrected={fixed} marker={marker_new}"

def main() -> None:
    counts = measure()
    import sys

    sys.path.insert(0, str(ROOT / "tools"))
    from freshness import compute_source_identity  # noqa: PLC0415

    head = compute_source_identity(ROOT).source_head

    # --- Home: the badge follows the canonical README/VERSION/CHANGELOG ------
    _replace(
        "Home.md",
        "**v8.1.0** | MIT | [Spec]",
        "**v8.2.0** | MIT | [Spec]",
        "Home: badge v8.1.0 -> v8.2.0",
    )
    _replace(
        "Home.md",
        "## Key features v8.1.0",
        "## Key features v8.2.0",
        "Home: Key features heading",
    )

    # --- Home: the v8.2.0 feature bullet, after the v8.1.0 one ---------------
    _replace(
        "Home.md",
        "- **Public installation and removal** (v8.1.0): the documented install, "
        "set, cold continue, validate, uninstall and reinstall lifecycle runs "
        "through the installed launchers on Windows, macOS, Linux and Git Bash; "
        "removal strips the marked block, hook entries and unchanged installed "
        "files while preserving settings, hooks, skills, edits, backups and "
        "project memory; the exact tagged commit must validate before GitHub "
        "releases.",
        "- **Public installation and removal** (v8.1.0): the documented install, "
        "set, cold continue, validate, uninstall and reinstall lifecycle runs "
        "through the installed launchers on Windows, macOS, Linux and Git Bash; "
        "removal strips the marked block, hook entries and unchanged installed "
        "files while preserving settings, hooks, skills, edits, backups and "
        "project memory; the exact tagged commit must validate before GitHub "
        "releases.\n"
        "- **Host acceptance tells execution from dispatch** (v8.2.0): the "
        "installed-host probe splits the six stages a successor turn actually "
        "has -- capability discovered, request persisted, host accepted, turn "
        "started, turn completed, multi-turn continuation -- and requires "
        "broker-verified event identity before any of them is claimed; a "
        "synthetic or model-written receipt is never acceptance, discovery is "
        "strictly read-only, and a registered `HOST_SCHEDULER_DISPATCH_CMD` / "
        "`HOST_DISPATCH_ENDPOINT` transport is consulted instead of one "
        "optimistic verdict (T-2011).",
        "Home: v8.2.0 feature bullet",
    )

    # --- Home: the inventory line, measured on today's bytes -----------------
    _replace(
        "Home.md",
        "- **Current tree inventory** (measured at this package's source binding, "
        "HEAD b152e6de over v8.1.0): 572 `tools/test_*.py` modules declaring 8311 "
        "test methods, and the mutation-control harness declares 276 full-sweep "
        "controls (`audit_checks.FULL_CASE_COUNT`) -- the release gate still runs "
        "the full sweep, and a scoped run never prints the \"N of\" total, so it "
        "is never release evidence.",
        "- **Current tree inventory** (measured at this package's source binding, "
        f"HEAD {head[:8]} over v8.2.0): "
        f"{counts['modules']} `tools/test_*.py` modules declaring "
        f"{counts['methods']} test methods, and the mutation-control harness "
        f"declares {counts['controls']} full-sweep controls "
        "(`audit_checks.FULL_CASE_COUNT`) -- the release gate still runs the full "
        "sweep, and a scoped run never prints the \"N of\" total, so it is never "
        "release evidence.",
        "Home: re-measured inventory",
    )

    # --- _Footer: the version string follows the same canonical surfaces -----
    _replace(
        "_Footer.md",
        "SAIPEN v8.1.0 — One command. Zero dependencies. Zero amnesia. — MIT",
        "SAIPEN v8.2.0 — One command. Zero dependencies. Zero amnesia. — MIT",
        "_Footer: version v8.1.0 -> v8.2.0",
    )

    # --- SubSaipen: this producer's own status row, rebound to W-053 ---------
    _replace(
        "SubSaipen.md",
        "| **saiwiki** | Wiki producer | FORCE-FRESH maintains all 9 wiki pages. "
        "W-052 re-binds the package to the current source triple after 38 commits "
        "moved it past W-051's binding; the Scenarios mirror covers 257 canonical "
        "rows at digest sha256:f46193d66010358e, and the inventory is re-measured "
        "on today's bytes (572 modules / 8311 test methods / 276 controls) — "
        "ready in OUTBOX, not integrated or pushed. |",
        "| **saiwiki** | Wiki producer | FORCE-FRESH maintains all 9 wiki pages. "
        "W-053 re-binds the package to the current source triple (HEAD "
        f"{head[:8]}, tree over v8.2.0) after the pending v8.2.0 release batch "
        "moved VERSION/README/CHANGELOG and one commit landed past W-052's "
        "binding; the Scenarios mirror covers 257 canonical rows at digest "
        "sha256:f46193d66010358e, and the inventory is re-measured on today's "
        f"bytes ({counts['modules']} modules / {counts['methods']} test methods / "
        f"{counts['controls']} controls) — ready in OUTBOX, not integrated or "
        "pushed. |",
        "SubSaipen: saiwiki row -> W-053",
    )

    scenarios = refresh_scenarios()
    print(
        json.dumps(
            {
                "applied": APPLIED,
                "already": ALREADY,
                "counts": counts,
                "head": head,
                "scenarios": scenarios,
            },
            indent=2,
        )
    )

if __name__ == "__main__":
    main()
