"""Every production refusal code is registered, and no refusal crashes (T-1437).

Measured on SAITULS: the source-gate pass-through called
``_refuse("SOURCE_LINKAGE_DRIFT")`` while that code was absent from
REGISTRY.json's ``error_codes``, so ``Result.__post_init__`` raised ValueError
and an ordinary refusal died as a traceback instead of a structured result.

Two contracts hold here:

  REGISTRY COMPLETENESS
      every statically discoverable refusal literal in production code
      (tools/saipen.py + tools/saipen_engine/**, not tests) belongs to the
      canonical ``error_codes`` registry;

  STRUCTURED REFUSAL
      constructing a refusal never raises and never becomes a silent generic
      success: a registered code yields the ordinary Result, an unregistered
      one is returned as a refusal MARKED with ``unregistered_code`` so the
      developer-facing completeness test -- not a production traceback -- is
      what fails loudly.

Run standalone:
    python tools/test_refusal_registry.py
"""

from __future__ import annotations

import ast
import re
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.errors import CODES  # noqa: E402
from saipen_engine.result import Result  # noqa: E402

PRODUCTION_ROOTS = [TOOLS / "saipen.py", TOOLS / "saipen_engine"]


def _iter_sources():
    for root in PRODUCTION_ROOTS:
        if root.is_file():
            yield root
        else:
            for path in sorted(root.rglob("*.py")):
                if "__pycache__" in path.parts:
                    continue
                yield path


def _literal_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _module_constants(tree: ast.Module) -> dict[str, str]:
    """Module-level `NAME = "literal"` assignments, for name-resolved codes.

    A refusal code written as a constant is not less of a refusal code than the
    same string inlined: `_decision_wait` answers `WAIT_OPERATOR` from
    `entry.WAIT_OPERATOR`, so a literal-only scan reported the registry complete
    while eleven such codes reached callers marked `unregistered_code`.
    """
    constants: dict[str, str] = {}
    for node in tree.body:
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1):
            continue
        target = node.targets[0]
        value = _literal_str(node.value)
        if isinstance(target, ast.Name) and value is not None:
            constants[target.id] = value
    return constants


def _code_of(node: ast.AST | None, constants: dict[str, str]) -> str | None:
    """The code a construction site names: a literal, or a module constant."""
    if node is None:
        return None
    value = _literal_str(node)
    if value is not None:
        return value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    return None


def _code_first_helpers(tree: ast.Module) -> set[str]:
    """Local helpers whose FIRST value parameter is the refusal code.

    A helper named `refuse` is not automatically code-first:
    `host_authority_identity.refuse(reason, detail)` returns a proof step, and
    `saipen.refuse(detail)` is message-first. Reading the parameter name is the
    only way to tell a refusal code from prose or a proof-step reason.
    """
    helpers: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        params = [arg.arg for arg in node.args.args]
        if params[:1] == ["self"]:
            params = params[1:]
        if params[:1] == ["code"]:
            helpers.add(node.name)
    return helpers


def _refusal_literals(tree: ast.AST, constants: dict[str, str] | None = None) -> set[str]:
    """Production refusal codes, by construction shape.

    Only code-shaped values count (`[A-Z][A-Z0-9_]*`): a usage sentence
    passed to a message-first local helper is not a refusal code, and the
    engine's `_refuse(code, detail)` plus the `{"ok": False, "code": ...}`
    dict shape are the two construction sites the measured crash travelled.
    A code named through a module-level constant is resolved, never skipped.
    """
    consts = constants or {}
    code_first = _code_first_helpers(tree) if isinstance(tree, ast.Module) else set()
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            keys = [k.value if isinstance(k, ast.Constant) else None for k in node.keys]
            if "ok" in keys and "code" in keys:
                ok_value = node.values[keys.index("ok")]
                code_value = node.values[keys.index("code")]
                if isinstance(ok_value, ast.Constant) and ok_value.value is False:
                    value = _code_of(code_value, consts)
                    if value is not None:
                        found.add(value)
            continue
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name in ("_refuse", "refuse"):
            # Two local helper shapes share these names; only a code-first one
            # is a refusal, and the dict shape above already covers the rest.
            if name not in code_first:
                continue
            for arg in node.args:
                value = _code_of(arg, consts)
                if value is not None:
                    found.add(value)
                    break
        if name == "Result":
            keywords = {kw.arg: kw.value for kw in node.keywords}
            ok = keywords.get("ok")
            if isinstance(ok, ast.Constant) and ok.value is False:
                value = _code_of(keywords.get("code"), consts)
                if value is not None:
                    found.add(value)
        if name == "EngineError":
            keywords = {kw.arg: kw.value for kw in node.keywords}
            value = _code_of(keywords.get("code"), consts)
            if value is not None:
                found.add(value)
    return {code for code in found if re.fullmatch(r"[A-Z][A-Z0-9_]*", code)}


def discovered_production_codes() -> set[str]:
    codes: set[str] = set()
    for path in _iter_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        codes |= _refusal_literals(tree, _module_constants(tree))
    return codes


class RegistryCompletenessTests(unittest.TestCase):
    def test_every_production_refusal_code_is_registered(self) -> None:
        discovered = discovered_production_codes()
        missing = sorted(code for code in discovered if code not in CODES)
        self.assertEqual(
            missing,
            [],
            "production refusal codes absent from REGISTRY.json error_codes: "
            + ", ".join(missing),
        )

    def test_the_scan_actually_sees_the_measured_case(self) -> None:
        """The discovery is not vacuously green: the SAITULS code is found."""
        self.assertIn("SOURCE_LINKAGE_DRIFT", discovered_production_codes())

    def test_a_code_named_through_a_module_constant_is_discovered(self) -> None:
        """The second measured case: a constant-shaped code, not a literal.

        `entry._decision_wait` answers `WAIT_OPERATOR` through the module
        constant, so a literal-only discovery called the registry complete
        while that code reached callers marked `unregistered_code`.
        """
        discovered = discovered_production_codes()
        self.assertIn("WAIT_OPERATOR", discovered)
        self.assertIn("WAIT_FOREIGN_OWNER", discovered)

    def test_the_constant_resolver_reads_the_name_not_the_shape(self) -> None:
        """A name is resolved to its module value; an unknown name is silent."""
        tree = ast.parse(
            'CODE = "PROBE_UNREGISTERED"\n'
            'OTHER = "not-a-code"\n'
            'a = {"ok": False, "code": CODE}\n'
            'b = {"ok": False, "code": OTHER}\n'
            'c = {"ok": False, "code": UNKNOWN_NAME}\n'
        )
        self.assertEqual(
            _refusal_literals(tree, _module_constants(tree)), {"PROBE_UNREGISTERED"}
        )


class StructuredRefusalTests(unittest.TestCase):
    def test_source_linkage_drift_is_a_structured_refusal(self) -> None:
        result = Result.refuse("SOURCE_LINKAGE_DRIFT", "linkage drift")
        payload = result.to_dict()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["code"], "SOURCE_LINKAGE_DRIFT")
        self.assertNotIn("unregistered_code", payload)

    def test_unknown_refusal_code_never_crashes_but_is_marked(self) -> None:
        result = Result(ok=False, code="NOT_A_REGISTERED_CODE", message="probe")
        payload = result.to_dict()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["code"], "NOT_A_REGISTERED_CODE")
        self.assertTrue(payload.get("unregistered_code"))
        self.assertNotEqual(payload["code"], "VALIDATION_FAILED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
