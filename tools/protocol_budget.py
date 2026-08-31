#!/usr/bin/env python
"""Measure every registry-declared SAIPEN runtime load profile."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _protocol_dir(protocol_dir: Path | None = None) -> Path:
    if protocol_dir is not None:
        return Path(protocol_dir)
    here = Path(__file__).resolve()
    candidate = here.parent.parent / "saipen"
    return candidate if candidate.is_dir() else here.parent / "saipen"


def _size(path: Path) -> int:
    return path.stat().st_size if path.is_file() else 0


def _load_graph(protocol_dir: Path) -> dict[str, Any]:
    path = protocol_dir / "REGISTRY.json"
    registry = json.loads(path.read_text(encoding="utf-8-sig"))
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


def _measure_route(
    protocol_dir: Path, surfaces: dict[str, Any], route: dict[str, Any]
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
    must_sizes = {item: _token_size(protocol_dir, surfaces, item) for item in must}
    conditional_sizes = {
        item: _token_size(protocol_dir, surfaces, item) for item in conditional
    }
    return {
        "name": str(route.get("name", "")),
        "bytes": sum(must_sizes.values()),
        "must": must_sizes,
        "conditional": conditional_sizes,
        "exclude": excluded,
    }


def load_profiles(protocol_dir: Path | None = None) -> dict[str, Any]:
    base = _protocol_dir(protocol_dir)
    graph = _load_graph(base)
    surfaces = graph["surfaces"]
    measured: dict[str, int] = {}
    detail: dict[str, list[dict[str, Any]]] = {}
    for name, profile in graph["profiles"].items():
        routes = profile.get("routes") if isinstance(profile, dict) else None
        if not isinstance(routes, list) or not routes:
            raise ValueError(f"load profile {name!r} must declare at least one route")
        route_detail = [_measure_route(base, surfaces, route) for route in routes]
        detail[name] = route_detail
        measured[name] = max(route["bytes"] for route in route_detail)
    return {
        **measured,
        "profiles": detail,
        "budgets": graph["budgets"],
        "basis": graph.get("basis", ""),
        "core": _size(base / "CORE.md"),
        "boot": _size(base / "BOOT.md"),
        "phases_total": sum(_size(path) for path in (base / "phases").glob("*.md")),
        "human_markdown_total": sum(_size(path) for path in base.rglob("*.md")),
    }


def check(protocol_dir: Path | None = None) -> list[str]:
    measured = load_profiles(protocol_dir)
    return [
        f"{name} {measured[name]} > {limit}"
        for name, limit in measured["budgets"].items()
        if measured[name] > limit
    ]


if __name__ == "__main__":
    import sys

    errors = check()
    print(json.dumps(load_profiles(), indent=2))
    if errors:
        print("BUDGET FAIL:", "; ".join(errors), file=sys.stderr)
        sys.exit(1)
    print("BUDGET PASS")
