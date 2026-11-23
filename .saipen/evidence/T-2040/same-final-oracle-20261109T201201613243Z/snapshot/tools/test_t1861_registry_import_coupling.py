"""T-1861: the registry a module import REQUIRES must be the registry on disk.

T-1857's reported crash was ``REGISTRY.json `limits` must be an object`` raised
at import time from ``goal_authority.py``. The root cause was generation drift:
the worktree code read ``goal_authority.limits`` while the registry it resolved
did not carry that block. Every command entry point imports the engine, so one
missing block takes the whole protocol offline -- and nothing failed first.

The gap is structural, not specific to ``limits``. Engine modules call
``require_mapping(load_registry(), "...")`` at module scope, and they nest it
(``require_mapping(require_mapping(load_registry(), "goal_authority"), "limits")``).
A test per block would drift out of date the moment someone adds the next one,
so this test derives the requirement from the SOURCE: it resolves each
module-scope guard call to a dotted registry path and asserts the real
REGISTRY.json supplies an object at that path.

Red control: delete a discovered block from a copy and assert the same check
reports it missing. Without that, a scan that silently found nothing would
pass forever.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
ENGINE = TOOLS / "saipen_engine"
REGISTRY = REPO / "saipen" / "REGISTRY.json"

#: Guard calls that resolve the registry at import time and fail hard if the
#: block is absent or of the wrong shape, mapped to the type they demand.
#: The OUTERMOST guard in a nested expression decides the expected shape.
GUARDS = {
    "require_mapping": dict,
    "require_string_list": list,
}


def _literal(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return node.func.id
    return None


def _resolve_path(
    node: ast.AST, bindings: dict[str, tuple[tuple[str, ...], type]] | None = None
) -> tuple[tuple[str, ...], type] | None:
    """(registry path, required type) that ``node`` demands, or None if unprovable.

    ``load_registry()`` is the root. Each guard call contributes its literal
    keys AND the shape it insists on, so the nested form
    ``require_mapping(require_mapping(load_registry(), "goal_authority"), "limits")``
    yields two requirements: ``goal_authority`` as a dict and
    ``goal_authority.limits`` as a dict. A ``require_string_list`` outermost
    demands a list, which is a different contract, not a weaker one.

    `bindings` follows the module-level aliases real modules use to keep their
    import block readable::

        _REGISTRY = load_registry()
        _STATE_REGISTRY = require_mapping(_REGISTRY, "state")
        STATE_REQUIRED_FIELDS = require_string_list(_STATE_REGISTRY, "required_fields")

    Without it the scan saw only chains rooted directly at `load_registry()`,
    so `state.py` and `evidence.py` contributed ZERO requirements while their
    import block demanded seven. The guard would have passed forever as those
    two modules drifted -- unable to see the modules it exists to guard.
    """
    if _call_name(node) == "load_registry":
        return (), dict  # the registry root is the mapping every guard reads from
    if isinstance(node, ast.Name) and bindings is not None:
        bound = bindings.get(node.id)
        if bound is not None:
            return bound
    guard = _call_name(node)
    if guard not in GUARDS:
        return None
    args = node.args
    if not args:
        return None
    inner = _resolve_path(args[0], bindings)
    if inner is None:
        return None
    base, _ = inner
    keys = [key for key in (_literal(arg) for arg in args[1:]) if key is not None]
    if not keys:
        return None
    return base + tuple(keys), GUARDS[guard]


def module_scope_requirements(source: str) -> tuple[dict[tuple[str, ...], type], bool]:
    """(required path -> required type, whether the module touches the registry)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}, False

    paths: dict[tuple[str, ...], type] = {}
    touches = False

    # Aliases first, in source order: a binding may chain off an earlier one.
    # Only module-scope assignments participate; a local name proves nothing.
    bindings: dict[str, tuple[tuple[str, ...], type]] = {}
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            target = statement.targets[0]
            if isinstance(target, ast.Name):
                resolved = _resolve_path(statement.value, bindings)
                if resolved is not None:
                    bindings[target.id] = resolved
                    if resolved[0]:
                        paths[resolved[0]] = resolved[1]

    def walk(node: ast.AST) -> None:
        nonlocal touches
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            return  # runs on call, not import: out of scope
        if _call_name(node) == "load_registry":
            touches = True
        resolved = _resolve_path(node, bindings)
        if resolved is not None:
            path, required = resolved
            if path:
                paths[path] = required
        for child in ast.iter_child_nodes(node):
            walk(child)

    for statement in tree.body:
        walk(statement)
    return paths, touches


def discovered_requirements(
    engine: Path = ENGINE,
) -> tuple[dict[str, dict[tuple[str, ...], type]], set[str]]:
    """({module: {dotted path: required type}}, {modules touching the registry})."""
    out: dict[str, dict[tuple[str, ...], type]] = {}
    touching: set[str] = set()
    for path in sorted(engine.glob("*.py")):
        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            continue
        paths, touches = module_scope_requirements(source)
        if paths:
            out[path.name] = paths
        if touches:
            touching.add(path.name)
    return out, touching


def lookup(registry: dict, path: tuple[str, ...]):
    node = registry
    for key in path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def missing_blocks(
    requirements: dict[str, dict[tuple[str, ...], type]], registry: dict
) -> list[str]:
    problems = []
    for module, paths in sorted(requirements.items()):
        for path, required in sorted(paths.items()):
            found = lookup(registry, path)
            if not isinstance(found, required):
                dotted = ".".join(path)
                problems.append(
                    f"{module} requires REGISTRY.json `{dotted}` to be a "
                    f"{required.__name__} at import time, registry has "
                    f"{type(found).__name__}"
                )
    return problems


class RegistryImportCouplingTests(unittest.TestCase):
    def test_scan_finds_the_known_requirement(self) -> None:
        """The scanner must see goal_authority.limits -- the block that crashed."""
        reqs, _ = discovered_requirements()
        self.assertIn("goal_authority.py", reqs, "scanner missed goal_authority.py")
        self.assertIn(
            ("goal_authority", "limits"),
            reqs["goal_authority.py"],
            "scanner missed the nested goal_authority.limits requirement",
        )

    def test_scan_is_not_vacuous(self) -> None:
        reqs, touching = discovered_requirements()
        total = sum(len(v) for v in reqs.values())
        self.assertGreaterEqual(
            len(touching), 5,
            f"only {len(touching)} modules touch the registry at import time; "
            "the scan is probably broken",
        )
        self.assertGreaterEqual(
            total, 6,
            f"only {total} resolvable requirements found; the scan is probably broken",
        )

    def test_module_scope_aliases_are_followed(self) -> None:
        """A guard rooted at an ALIAS, not at `load_registry()`, must still resolve.

        Measured on this repository before the fix: 6 requirements over 4
        modules, while `state.py` (ten demands) and `evidence.py` (two) resolved
        to NOTHING because they bind `_REGISTRY = load_registry()` and then
        guard the alias. A scan that cannot follow the alias leaves the two
        heaviest registry consumers unguarded while still passing, so this
        asserts both modules are SEEN, not merely that the totals look healthy.
        """
        reqs, _ = discovered_requirements()
        self.assertIn("state.py", reqs, "scanner missed state.py entirely")
        self.assertIn("evidence.py", reqs, "scanner missed evidence.py entirely")
        self.assertIn(("state", "required_fields"), reqs["state.py"])
        self.assertIn(("state", "known_fields"), reqs["state.py"])
        self.assertIn(("evidence_retention", "classifications"), reqs["evidence.py"])
        # The alias chain is what makes these visible; without it they vanish.
        self.assertGreaterEqual(
            sum(len(v) for v in reqs.values()), 20,
            "the scan lost alias-rooted requirements -- registry consumers are "
            "unguarded again",
        )

    def test_control_detects_a_missing_alias_rooted_block(self) -> None:
        """Red control: a block seen only through an alias must also be checked."""
        reqs, _ = discovered_requirements()
        registry = json.loads(REGISTRY.read_text(encoding="utf-8-sig"))
        damaged = json.loads(json.dumps(registry))
        damaged["state"].pop("required_fields", None)
        problems = missing_blocks(reqs, damaged)
        self.assertTrue(
            problems, "control failed: deleting state.required_fields was not detected"
        )
        self.assertIn("state.required_fields", " ".join(problems))

    def test_every_import_time_requirement_is_present(self) -> None:
        reqs, _ = discovered_requirements()
        registry = json.loads(REGISTRY.read_text(encoding="utf-8-sig"))
        problems = missing_blocks(reqs, registry)
        self.assertEqual(
            problems,
            [],
            "the registry on disk cannot satisfy the engine it ships with:\n  "
            + "\n  ".join(problems),
        )

    def test_control_detects_a_deleted_block(self) -> None:
        """Red control: remove a required block and the check must report it."""
        reqs, _ = discovered_requirements()
        registry = json.loads(REGISTRY.read_text(encoding="utf-8-sig"))
        self.assertEqual(
            missing_blocks(reqs, registry), [], "precondition: the live pair is consistent"
        )

        self.assertIn(("goal_authority", "limits"), reqs["goal_authority.py"])
        damaged = json.loads(json.dumps(registry))
        damaged["goal_authority"].pop("limits", None)
        problems = missing_blocks(reqs, damaged)
        self.assertTrue(problems, "control failed: deleting goal_authority.limits was not detected")
        self.assertIn("goal_authority.limits", " ".join(problems))

    def test_control_detects_a_deleted_top_level_block(self) -> None:
        """Second control: a whole top-level block removal is also detected."""
        reqs, _ = discovered_requirements()
        registry = json.loads(REGISTRY.read_text(encoding="utf-8-sig"))
        self.assertIn(("phases",), reqs.get("phases.py", {}))

        damaged = json.loads(json.dumps(registry))
        damaged.pop("phases", None)
        self.assertTrue(
            missing_blocks(reqs, damaged),
            "control failed: deleting `phases` was not detected",
        )

    def test_the_reported_command_path_imports(self) -> None:
        """The exact entry point the operator reported must import cleanly."""
        result = subprocess.run(
            [
                sys.executable, "-B", "-c",
                "import sys; sys.path.insert(0, 'tools'); "
                "from saipen_engine import goal_authority; "
                "print(goal_authority.GOAL_WAVE_CAP, goal_authority.GOAL_TICKET_CAP)",
            ],
            cwd=REPO, capture_output=True, text=True, timeout=180,
        )
        self.assertEqual(
            result.returncode, 0,
            f"importing goal_authority failed:\n{result.stderr[-2000:]}",
        )
        waves, tickets = result.stdout.split()
        self.assertEqual((int(waves), int(tickets)), (3, 20))


if __name__ == "__main__":
    unittest.main(verbosity=2)
