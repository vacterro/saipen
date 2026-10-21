"""Conservative, generation-bound impact selection; uncertainty requires FULL.

Narrow selection is certified only in a closed static import/call domain.
Arbitrary Python, file/reflection dependencies and protocol boundaries are not
guessed from extensions or import edges. A plan executes nothing and grants no
acceptance. Actual selected runs remain focused evidence, never full evidence.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import sys
from contextlib import suppress
from pathlib import Path, PurePosixPath

_BUILTINS = frozenset({
    "abs", "all", "any", "bool", "dict", "enumerate", "float", "frozenset", "int",
    "isinstance", "issubclass", "len", "list", "max", "min", "range", "repr", "reversed",
    "round", "set", "sorted", "str", "sum", "tuple", "zip", "object", "super",
    "ValueError", "TypeError", "AssertionError", "RuntimeError", "Exception",
})
_METHODS = frozenset({
    "append", "extend", "get", "items", "keys", "values", "copy", "count", "index",
    "split", "join", "strip", "startswith", "endswith", "lower", "upper", "replace",
    "assertEqual", "assertNotEqual", "assertTrue", "assertFalse", "assertIs", "assertIsNot",
    "assertIsNone", "assertIsNotNone", "assertIn", "assertNotIn", "assertRaises",
    "assertRaisesRegex", "assertGreater", "assertLess", "assertGreaterEqual", "assertLessEqual",
    "assertAlmostEqual", "assertCountEqual", "assertIsInstance", "subTest", "fail",
    "setUp", "tearDown",
})
_STDLIB = {
    "__future__": {"annotations"},
    "unittest": {"TestCase", "skip", "skipIf", "skipUnless", "expectedFailure", "SkipTest"},
    "math": {"ceil", "floor", "sqrt", "isfinite", "isclose", "sin", "cos", "pi", "e"},
    "operator": {"add", "sub", "mul", "truediv"},
    "json": {"loads", "dumps"},
}
_BOUNDARY = re.compile(
    r"(?:validate|validator|fixture|conftest|admission|authority|guard|protocol|verification|"
    r"release|closure|baseline|registry|runtime|router|core_unit|test_runner|acceptance|operations)"
)
_FIXTURES = {"setUpModule", "tearDownModule", "setUpClass", "tearDownClass", "load_tests"}


def digest(value) -> str:
    content = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(content).hexdigest()


def _paths(changed):
    if not isinstance(changed, list):
        raise ValueError("changed paths must be a list")
    normalized = set()
    for raw in changed:
        if not isinstance(raw, str) or not raw:
            raise ValueError("changed path must be nonempty text")
        value = raw.replace("\\", "/")
        path = PurePosixPath(value)
        if path.is_absolute() or ":" in value or ".." in path.parts or str(path) == ".":
            raise ValueError("changed paths must remain inside the project")
        normalized.add(str(path))
    return sorted(normalized)


def git_changes(root: Path) -> list[str]:
    """Tracked plus added/untracked paths, without modifying the index or tree."""
    changes = []
    for command in (("diff", "--name-only", "-z", "HEAD", "--"),
                    ("ls-files", "--others", "--exclude-standard", "-z")):
        try:
            result = subprocess.run(["git", "-C", str(root), *command], stdin=subprocess.DEVNULL,
                                    capture_output=True, text=True, encoding="utf-8",
                                    errors="replace", timeout=30, check=False)
        except OSError:
            raise ValueError("Git unavailable; use an explicit --changed scope") from None
        if result.returncode:
            raise ValueError(
                "Git cannot establish changed paths; supply an explicit --changed scope"
            )
        changes.extend(value for value in result.stdout.split("\0") if value
                       and value.split("/")[0] not in {".git", ".saipen"})
    return _paths(changes)


def _module(path: str) -> str:
    parts = list(PurePosixPath(path).relative_to("tools").with_suffix("").parts)
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _chain(node):
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.Attribute) and (base := _chain(node.value)):
        return [*base, node.attr]
    return None


class _StaticDomain(ast.NodeVisitor):
    def __init__(self, name, modules):
        self.name, self.modules = name, modules
        self.dependencies, self.unknown = set(), set()
        self.aliases = {}
        self.definitions = set()
        self.fixtures = set()
        self.parents = {}

    def issue(self, node, text):
        self.unknown.add(f"line {node.lineno}: {text}")

    def dependency(self, name, node):
        if name not in self.modules:
            self.issue(node, f"unresolved import {name}")
            return False
        self.dependencies.add(name)
        parts = name.split(".")
        self.dependencies.update(".".join(parts[:i]) for i in range(1, len(parts))
                                 if ".".join(parts[:i]) in self.modules)
        return True

    def visit_Import(self, node):
        for alias in node.names:
            root = alias.name.split(".")[0]
            if root in sys.stdlib_module_names and root in self.modules:
                self.issue(node, f"standard-library/project import collision {root}")
                self.dependency(root, node)
            elif alias.name in _STDLIB:
                self.aliases[alias.asname or alias.name] = ("stdlib", alias.name)
            elif self.dependency(alias.name, node):
                self.aliases[alias.asname or alias.name.split(".")[0]] = ("project", alias.name)

    def visit_ImportFrom(self, node):
        base = node.module or ""
        if node.level:
            package = self.name.split(".")
            if not self.modules[self.name].endswith("/__init__.py"):
                package = package[:-1]
            base = ".".join([*package[:len(package) - node.level + 1], *base.split(".")]).strip(".")
        standard = not node.level and base in _STDLIB
        if not node.level and base.split(".")[0] in sys.stdlib_module_names \
                and base.split(".")[0] in self.modules:
            self.issue(node, f"standard-library/project import collision {base}")
            standard = False
        if not standard:
            self.dependency(base, node)
        for alias in node.names:
            if alias.name == "*":
                self.issue(node, "wildcard import has unknown exports")
            elif standard:
                if alias.name not in _STDLIB[base]:
                    self.issue(node, f"unproved standard-library API {base}.{alias.name}")
                self.aliases[alias.asname or alias.name] = ("symbol", base)
            else:
                child = f"{base}.{alias.name}"
                if child in self.modules:
                    self.dependency(child, node)
                self.aliases[alias.asname or alias.name] = ("project", child)

    def visit_If(self, node):
        # Canonical discovery imports modules; the conventional script entry
        # is not executed. Reassigning __name__ is rejected below.
        test = node.test
        if (isinstance(test, ast.Compare) and isinstance(test.left, ast.Name)
                and test.left.id == "__name__" and len(test.ops) == 1
                and isinstance(test.ops[0], ast.Eq) and len(test.comparators) == 1
                and isinstance(test.comparators[0], ast.Constant)
                and test.comparators[0].value == "__main__"):
            for item in node.orelse:
                self.visit(item)
            return
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self.definitions.add(node.name)
        if node.name in _FIXTURES:
            self.fixtures.add(node.name)
        if node.name in {"load_tests", "__getattr__", "__getattribute__", "__setattr__"}:
            self.issue(node, f"dynamic hook {node.name}")
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        self.definitions.add(node.name)
        self.generic_visit(node)

    def visit_Name(self, node):
        if node.id in {"__builtins__", "__file__", "__loader__", "__spec__"}:
            self.issue(node, f"reflective context {node.id}")
        if isinstance(node.ctx, ast.Store) and node.id.startswith("__"):
            self.issue(node, "magic module/class namespace reassignment")
        if (isinstance(node.ctx, ast.Store)
                and node.id in _BUILTINS | self.aliases.keys() | self.definitions):
            self.issue(node, "callable/import binding reassignment")
        if isinstance(node.ctx, ast.Load) and self.aliases.get(node.id, (None,))[0] == "stdlib":
            parent = self.parents.get(node)
            if not isinstance(parent, ast.Attribute) or parent.value is not node:
                self.issue(node, "standard-library namespace escapes the closed domain")

    def visit_arg(self, node):
        if node.arg in _BUILTINS | self.aliases.keys() | self.definitions:
            self.issue(node, "callable binding shadowed by an argument")

    def visit_Attribute(self, node):
        chain = _chain(node)
        if node.attr.startswith("_"):
            self.issue(node, "private/reflection attribute")
        if isinstance(node.ctx, ast.Store) and (not chain or chain[0] not in {"self", "cls"}):
            self.issue(node, "unproved shared-object mutation")
        if chain and chain[0] in self.aliases:
            kind, module = self.aliases[chain[0]]
            if kind == "stdlib" and (len(chain) != 2 or chain[1] not in _STDLIB[module]):
                self.issue(node, "unproved standard-library attribute")
            if kind == "symbol":
                self.issue(node, "unproved attribute of imported standard-library symbol")
        elif not chain or chain[0] not in {"self", "cls"}:
            self.issue(node, "unproved object attribute")
        self.generic_visit(node)

    def visit_Call(self, node):
        function = node.func
        chain = _chain(function)
        if isinstance(function, ast.Name):
            if function.id not in _BUILTINS | self.definitions | self.aliases.keys():
                self.issue(node, f"unproved callable {function.id}")
        elif isinstance(function, ast.Attribute):
            if not chain or (chain[0] not in self.aliases and function.attr not in _METHODS):
                self.issue(node, f"unproved method {function.attr}")
        else:
            self.issue(node, "dynamic callable expression")
        self.generic_visit(node)


def plan(root: Path | str, changed: list[str]) -> dict:
    """Certify only the supplied change scope; bind every plan to current bytes."""
    from .core_unit import tree_fingerprint

    root = Path(root).resolve()
    changed = _paths(changed)
    fingerprint = tree_fingerprint(root)
    ignored = [value for value in changed if value.split("/")[0] in {".git", ".saipen"}]
    subjects = [value for value in changed if value not in ignored]
    modules, contents, hashes, unknown = {}, {}, {}, []
    tools = root / "tools"
    for path in sorted(tools.rglob("*.py")):
        relative = path.relative_to(root).as_posix()
        if len(modules) >= 5000:
            unknown.append("source inventory exceeds the bounded static domain")
            break
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents
                                    if parent != root):
            unknown.append(f"{relative}: symlink source cannot establish closed coverage")
            continue
        name = _module(relative)
        modules[name] = relative
        try:
            content = path.read_bytes()
            hashes[relative] = hashlib.sha256(content).hexdigest()
            contents[name] = content
        except OSError as exc:
            unknown.append(f"{relative}: {type(exc).__name__}")
    inventory = []
    for name, path in modules.items():
        file = PurePosixPath(path)
        if not file.name.startswith("test_"):
            continue
        parents = file.relative_to("tools").parts[:-1]
        if all((tools.joinpath(*parents[:i]) / "__init__.py").is_file()
               for i in range(1, len(parents) + 1)):
            inventory.append(name)
    inventory.sort()
    by_path = {path: name for name, path in modules.items()}
    for path in subjects:
        if (not path.startswith("tools/") or not path.endswith(".py")
                or _BOUNDARY.search(PurePosixPath(path).stem) or path not in by_path):
            unknown.append(f"{path}: verification/fixture/protocol or unknown source boundary")
    graph, fixtures, scanned = {}, {}, set()
    pending = list(reversed(inventory)) if subjects and not unknown else []
    while pending and not unknown:
        name = pending.pop()
        if name in scanned:
            continue
        scanned.add(name)
        try:
            tree = ast.parse(contents[name].decode("utf-8-sig"), filename=modules[name])
        except (KeyError, OSError, ValueError, SyntaxError) as exc:
            unknown.append(f"{modules.get(name, name)}: {type(exc).__name__}")
            break
        analysis = _StaticDomain(name, modules)
        analysis.parents = {child: parent for parent in ast.walk(tree)
                            for child in ast.iter_child_nodes(parent)}
        analysis.definitions.update(node.name for node in ast.walk(tree)
                                    if isinstance(node, (ast.FunctionDef, ast.ClassDef)))
        analysis.visit(tree)
        graph[name], fixtures[name] = analysis.dependencies, analysis.fixtures
        if analysis.unknown:
            details = sorted(analysis.unknown)
            unknown.append(f"{modules[name]}: {len(details)} unproved dependencies/effects; "
                           + "; ".join(details[:3]))
            break
        pending.extend(reversed(sorted(analysis.dependencies - scanned)))
    scan_complete = bool(inventory) and bool(subjects) and not unknown
    early_full = bool(unknown)

    def closure(names):
        seen, pending = set(), list(names)
        while pending:
            name = pending.pop()
            if name not in seen:
                seen.add(name)
                pending.extend(graph.get(name, ()))
        return seen

    test_closures = {name: closure([name]) for name in inventory}
    affected = {by_path[path] for path in subjects if path in by_path}
    selected, reasons = [], {}
    for name in inventory:
        hits = sorted(test_closures[name] & affected)
        if hits:
            selected.append(name)
            reasons[name] = [f"depends on {modules[hit]}" for hit in hits]
    for path in subjects:
        name = by_path.get(path)
        if (not path.startswith("tools/") or not path.endswith(".py")
                or _BOUNDARY.search(PurePosixPath(path).stem) or name is None
                or fixtures.get(name)):
            unknown.append(f"{path}: verification/fixture/protocol or unknown source boundary")
        elif not any(name in test_closures[test] for test in inventory):
            unknown.append(f"{path}: no proven static test consumer")
    if not inventory and subjects:
        unknown.append("no canonical test-module inventory")
    tier = "STATIC" if not subjects else "FULL" if unknown or not selected else "IMPACT"
    escalation = sorted(set(unknown)) if tier == "FULL" else []
    if tier == "IMPACT" and len(selected) == len(inventory):
        tier = "FULL"
        escalation.append("the required selection covers the complete canonical family")
    if tier == "FULL":
        selected = inventory[:]
        for name in selected:
            reasons.setdefault(name, []).append("full canonical selection required")
    selectors = sorted(closure(selected))
    focused_tests = [name for name in selected
                     if name in affected or graph.get(name, set()) & affected]
    if tree_fingerprint(root) != fingerprint:
        raise ValueError("source generation changed during impact analysis")
    return {
        "schema": 1, "kind": "conservative-impact-plan", "executed": False,
        "scope": "supplied changed paths; unlisted changes are not certified",
        "fingerprint": fingerprint, "changed": changed, "ignored": ignored,
        "tier": tier, "test_inventory": inventory, "selected_tests": selected,
        "scope_family": "unit", "focused_tests": focused_tests,
        "integration_tests": [name for name in selected if name not in focused_tests],
        "selector_modules": selectors, "selection_reasons": reasons,
        "unknown_coverage": sorted(set(unknown)),
        "escalation_reasons": escalation,
        "source_inventory_sha256": digest(hashes),
        "dependency_information": "closed static domain only; no dynamic completeness assumed",
        "dependency_scan_complete": scan_complete,
        "scanned_dependency_modules": sorted(scanned),
        "dependency_files": {name: modules[name] for name in sorted(scanned) if name in modules},
        "early_full_escalation": early_full,
        "historical_failure_policy": "historical failures never justify omitting coverage",
        "escalation_requirements": ["FULL unit family"] if tier == "FULL" else [],
        "contracts": ["canonical unit discovery and fixtures", "import failures always selected",
                      "focused evidence remains distinct from full publication evidence"],
    }


def problem(root, selection):
    if not isinstance(selection, dict) or selection.get("kind") != "conservative-impact-plan":
        return "missing impact selection contract"
    if selection.get("tier") != "IMPACT":
        return "impact selection requires a broader or different verification tier"
    try:
        current = plan(root, selection.get("changed"))
    except (OSError, ValueError) as exc:
        return str(exc)
    return None if current == selection else "impact plan is stale, incomplete or modified"


def manifest_problem(selection, run):
    """Prove the exact filtered canonical discovery, including imported cases."""
    manifest = run.get("manifest")
    if not isinstance(manifest, dict):
        return "impact discovery manifest is missing"
    inventory = manifest.get("inventory")
    if (not isinstance(inventory, list) or not inventory
            or any(not isinstance(item, (list, tuple)) or len(item) != 2
                   or any(not isinstance(value, str) for value in item) for item in inventory)):
        return "impact discovery inventory is invalid"
    if manifest.get("inventory_sha256") != digest(inventory):
        return "impact discovery inventory digest disagrees"
    requested = selection["selector_modules"]
    if manifest.get("requested_modules") != requested:
        return "impact selector differs from its bound plan"
    if (manifest.get("expected_module_paths") != selection["dependency_files"]
            or manifest.get("dependency_origin_errors")
            or manifest.get("module_origins") != selection["dependency_files"]):
        return "impact runtime dependency origins do not match the analyzed source"
    errors = manifest.get("import_error_indices")
    if (not isinstance(errors, list) or any(type(i) is not int or not 0 <= i < len(inventory)
                                          for i in errors) or len(set(errors)) != len(errors)):
        return "impact import-error inventory is invalid"
    expected = [index for index, item in enumerate(inventory)
                if item[1] in requested or index in errors]
    if (manifest.get("selected_indices") != expected or not expected
            or manifest.get("selected") != len(expected)
            or manifest.get("discovered") != len(inventory)
            or run.get("ran") != len(expected)):
        return "impact execution omits or duplicates required canonical occurrences"
    if errors and run.get("status") == "PASS":
        return "impact execution cannot pass with an import error"
    return None


def command(root, args):
    """Read-only plans, or existing focused execution for a certified subset."""
    from . import core_unit, focused_unit

    try:
        changes = args.changed or git_changes(root)
        if args.changed:
            # Even an explicitly scoped iteration must not silently omit newly
            # added/modified tests visible to the repository's own change list.
            with suppress(ValueError):
                changes = sorted(set(changes) | {path for path in git_changes(root)
                                                if PurePosixPath(path).name.startswith("test_")})
        selection = plan(root, changes)
        if args.plan:
            return core_unit._emit({"ok": True, "executed": False, "selection": selection})
        if selection["tier"] != "IMPACT":
            return core_unit._emit({
                "ok": False, "executed": False, "selection": selection,
                "detail": "impact coverage is not a certified subset; no verification was executed",
                "required_command": [sys.executable, "-B", "tools/core_unit.py", "evidence",
                                     args.ticket, "--project-root", str(root)]
                if selection["tier"] == "FULL" else None,
            })
        args.pattern = ["test_*.py"]
        args.impact_selection = selection
        return focused_unit.evidence(root, args)
    except (OSError, ValueError) as exc:
        return core_unit._emit({"ok": False, "executed": False, "detail": str(exc)})
