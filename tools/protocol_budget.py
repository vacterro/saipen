#!/usr/bin/env python
"""Measure every registry-declared SAIPEN runtime load profile.

The admission gate is the ROUTE (T-1670, SRC-191): what one execution route
mandatorily loads into an agent's context, measured against that route's
declared budget. A route's mandatory set is its `must` list closed over the
optional `load_profiles.requires` graph (document -> documents it always
loads), so a dependency a route pulls in transitively is counted without a
second hand-maintained list. `conditional` documents are reported and never
counted. The repository-wide `human_markdown_total` is reported as a growth
statistic only: a document no route loads costs no context, so growing it is
not a budget event. One guard stays global -- no single protocol document may
exceed the `single_doc` budget -- so removing the aggregate cap is never a
licence for one enormous file.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any


def _protocol_dir(protocol_dir: Path | None = None) -> Path:
    if protocol_dir is not None:
        return Path(protocol_dir)
    here = Path(__file__).resolve()
    candidate = here.parent.parent / "saipen"
    return candidate if candidate.is_dir() else here.parent / "saipen"


def _size(path: Path) -> int:
    """Content bytes with LF line ends (T-1465).

    `st_size` counted the checkout's line ends: with `text=auto` a file one
    tool rewrote carries CRLF on Windows and LF everywhere else, so
    REGISTRY.json measured 30496 bytes here and 29346 in a Linux clone, and a
    budget's verdict followed the checkout rather than the protocol.
    """
    if not path.is_file():
        return 0
    return len(path.read_bytes().replace(b"\r\n", b"\n"))


def _load_registry(protocol_dir: Path) -> dict[str, Any]:
    path = protocol_dir / "REGISTRY.json"
    registry = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(registry, dict):
        raise ValueError("REGISTRY.json root must be an object")
    return registry


def _load_graph(registry: dict[str, Any]) -> dict[str, Any]:
    graph = registry.get("load_profiles")
    if not isinstance(graph, dict) or graph.get("schema_version") != 1:
        raise ValueError("REGISTRY.json load_profiles schema is missing or unsupported")
    budgets = graph.get("budgets")
    profiles = graph.get("profiles")
    surfaces = graph.get("surfaces")
    if not all(isinstance(value, dict) for value in (budgets, profiles, surfaces)):
        raise ValueError("load_profiles budgets/profiles/surfaces must be objects")
    if set(budgets) != set(profiles):
        raise ValueError("every declared budget must have exactly one measured profile")
    return graph


def _phase_metrics(
    protocol_dir: Path, registry: dict[str, Any], graph: dict[str, Any]
) -> dict[str, Any]:
    phase_registry = registry.get("phases")
    phase_names = phase_registry.get("all") if isinstance(phase_registry, dict) else None
    if (
        not isinstance(phase_names, list)
        or not phase_names
        or any(not isinstance(name, str) or not name for name in phase_names)
        or len(set(phase_names)) != len(phase_names)
    ):
        raise ValueError("REGISTRY.json phases.all must be a unique string array")

    bytes_by_phase: dict[str, int] = {}
    for name in phase_names:
        path = protocol_dir / "phases" / f"{name.lower()}.md"
        if not path.is_file():
            raise ValueError(f"phase document does not exist: phases/{name.lower()}.md")
        bytes_by_phase[name] = _size(path)

    preferences = graph.get("phase_preferences", {})
    if not isinstance(preferences, dict):
        raise ValueError("load_profiles phase_preferences must be an object")
    bands = preferences.get("bands", {})
    if not isinstance(bands, dict):
        raise ValueError("load_profiles phase_preferences.bands must be an object")
    unknown = set(bands) - set(phase_names)
    if unknown:
        raise ValueError(
            "phase preference names are not registry phases: " + ", ".join(sorted(unknown))
        )
    for name, band in bands.items():
        if (
            not isinstance(band, dict)
            or not isinstance(band.get("min"), int)
            or not isinstance(band.get("max"), int)
            or band["min"] < 0
            or band["min"] > band["max"]
        ):
            raise ValueError(f"phase preference {name} needs integer min/max bytes")

    sizes = list(bytes_by_phase.values())
    largest_phase = min(bytes_by_phase, key=lambda name: (-bytes_by_phase[name], name))
    return {
        "bytes_by_phase": bytes_by_phase,
        "phases_count": len(bytes_by_phase),
        "phases_total": sum(sizes),
        "phases_median": statistics.median(sizes),
        "phases_max": bytes_by_phase[largest_phase],
        "largest_phase": largest_phase,
        "preferred_phase_bands": bands,
    }


def _surface_size(protocol_dir: Path, surfaces: dict[str, Any], name: str) -> int:
    spec = surfaces.get(name)
    if not isinstance(spec, dict) or spec.get("selection") != "max_one":
        raise ValueError(f"unknown or unsupported load surface @{name}")
    if "glob" in spec:
        paths = sorted(protocol_dir.glob(str(spec["glob"])))
    else:
        files = spec.get("files")
        if not isinstance(files, list) or any(not isinstance(item, str) for item in files):
            raise ValueError(f"load surface @{name} files must be a string array")
        paths = [protocol_dir / item for item in files]
    if not paths:
        raise ValueError(f"load surface @{name} resolves to no files")
    return max(_size(path) for path in paths)


def _token_size(protocol_dir: Path, surfaces: dict[str, Any], token: str) -> int:
    if token.startswith("@"):
        return _surface_size(protocol_dir, surfaces, token[1:])
    path = protocol_dir / token
    if not path.is_file():
        raise ValueError(f"load-profile document does not exist: {token}")
    return _size(path)


def _requires(graph: dict[str, Any]) -> dict[str, list[str]]:
    requires = graph.get("requires", {})
    if not isinstance(requires, dict) or any(
        not isinstance(doc, str)
        or doc.startswith("@")
        or not isinstance(deps, list)
        or any(not isinstance(dep, str) or dep.startswith("@") for dep in deps)
        for doc, deps in requires.items()
    ):
        raise ValueError("load_profiles requires must map a document to a document array")
    return requires


def _closure(must: list[str], requires: dict[str, list[str]]) -> list[str]:
    """`must` followed by every document it transitively requires, each once,
    in first-reached order. A cycle is a declaration error, never a loop."""
    ordered: list[str] = []
    seen: set[str] = set()

    def visit(token: str, path: tuple[str, ...]) -> None:
        if token in path:
            raise ValueError("load_profiles requires has a cycle: " + " -> ".join((*path, token)))
        if token in seen:
            return
        seen.add(token)
        ordered.append(token)
        for dep in requires.get(token, ()):
            visit(dep, (*path, token))

    for token in must:
        visit(token, ())
    return ordered


def _measure_route(
    protocol_dir: Path,
    surfaces: dict[str, Any],
    route: dict[str, Any],
    requires: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    must = route.get("must")
    conditional = route.get("conditional")
    excluded = route.get("exclude")
    if (
        not isinstance(must, list)
        or not isinstance(conditional, list)
        or not isinstance(excluded, list)
        or any(not isinstance(item, str) for item in [*must, *conditional, *excluded])
    ):
        raise ValueError("each load route needs string-array must/conditional/exclude")
    mandatory = _closure(must, requires or {})
    must_sizes = {item: _token_size(protocol_dir, surfaces, item) for item in mandatory}
    conditional_sizes = {
        item: _token_size(protocol_dir, surfaces, item) for item in conditional
    }
    return {
        "name": str(route.get("name", "")),
        "bytes": sum(must_sizes.values()),
        "must": must_sizes,
        "transitive": [item for item in mandatory if item not in must],
        "conditional": conditional_sizes,
        "exclude": excluded,
    }


def load_profiles(protocol_dir: Path | None = None) -> dict[str, Any]:
    base = _protocol_dir(protocol_dir)
    registry = _load_registry(base)
    graph = _load_graph(registry)
    surfaces = graph["surfaces"]
    requires = _requires(graph)
    documents = _documents(base)
    measured: dict[str, int] = {}
    detail: dict[str, list[dict[str, Any]]] = {}
    for name, profile in graph["profiles"].items():
        routes = profile.get("routes") if isinstance(profile, dict) else None
        if not isinstance(routes, list) or not routes:
            raise ValueError(f"load profile {name!r} must declare at least one route")
        route_detail = [_measure_route(base, surfaces, route, requires) for route in routes]
        detail[name] = route_detail
        measured[name] = max(route["bytes"] for route in route_detail)
    return {
        **measured,
        "profiles": detail,
        "budgets": graph["budgets"],
        "basis": graph.get("basis", ""),
        "core": _size(base / "CORE.md"),
        "boot": _size(base / "BOOT.md"),
        **_phase_metrics(base, registry, graph),
        "documents": documents,
        # Informational only (T-1670): repository growth, never admission.
        "human_markdown_total": sum(documents.values()),
        "informational": ["human_markdown_total"],
    }


def _documents(base: Path) -> dict[str, int]:
    return {path.relative_to(base).as_posix(): _size(path) for path in sorted(base.rglob("*.md"))}


def check(protocol_dir: Path | None = None) -> list[str]:
    """Every budget violation: a route over its declared budget, or one
    protocol document over `single_doc` whether or not a route loads it."""
    measured = load_profiles(protocol_dir)
    errors = [
        f"{name} {measured[name]} > {limit}"
        for name, limit in measured["budgets"].items()
        if measured[name] > limit
    ]
    file_limit = measured["budgets"].get("single_doc")
    if isinstance(file_limit, int):
        errors.extend(
            f"file {rel} {size} > single_doc {file_limit}"
            for rel, size in measured["documents"].items()
            if size > file_limit
        )
    return errors


def summary(protocol_dir: Path | None = None) -> list[str]:
    """The compact operator view: one line per route budget, then the
    informational repository total."""
    measured = load_profiles(protocol_dir)
    errors = set(check(protocol_dir))
    lines = []
    for name, limit in measured["budgets"].items():
        verdict = "FAIL" if f"{name} {measured[name]} > {limit}" in errors else "PASS"
        lines.append(f"{name:<20} {measured[name]:>6} / {limit:<6} {verdict}")
    largest = max(measured["documents"].items(), key=lambda item: (item[1], item[0]))
    lines.append(f"largest document     {largest[1]:>6}  {largest[0]}")
    lines.append(f"human markdown total {measured['human_markdown_total']:>6}  informational")
    lines.extend(sorted(error for error in errors if error.startswith("file ")))
    return lines


if __name__ == "__main__":
    import sys

    errors = check()
    if "--summary" in sys.argv[1:]:
        print("\n".join(summary()))
        sys.exit(1 if errors else 0)
    print(json.dumps(load_profiles(), indent=2))
    if errors:
        print("BUDGET FAIL:", "; ".join(errors), file=sys.stderr)
        sys.exit(1)
    print("BUDGET PASS")
