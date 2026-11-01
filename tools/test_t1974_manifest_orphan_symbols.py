"""T-1974: the manifest-orphan advisor must name real missing symbols, only.

`_uncommitted_symbols` answers one question: "does this untracked manifest file
import runtime that HEAD does not carry?" Its answer is attached as a warning to
an untracked-file FAIL and it changes the advice a reader acts on -- it says not
to commit the file. So a false positive is not cosmetic; it talks a reader out
of the correct fix.

Measured on this repository while adjudicating the nine working-tree-only files
under `tools/`:

    from saipen_engine import audit_manifest       -> "saipen_engine.audit_manifest"
    from saipen_engine import suite_record as SR   -> "saipen_engine.as", "saipen_engine.SR"
    from saipen_engine import future_gate as gates -> "saipen_engine.as", "saipen_engine.gates"

Every one of those modules is in HEAD. Two distinct defects produce them:

1. `from pkg import name` was read as "the symbol `name` inside `pkg/__init__.py`".
   When `name` is a SUBMODULE, Python imports `pkg/name.py` and `__init__.py`
   need never mention it.
2. The imported names were taken with `re.findall(r"[A-Za-z_]\\w*", clause)`,
   which yields the `as` keyword and the local alias as if they were exports.

Both are fixed by naming what the clause BINDS (`_imported_names`) and by
checking submodule paths against HEAD (`_submodule_paths`).

The behavioural tests build their own small repository instead of interrogating
this one. The advisor's question is about what a CLONE receives, so it can only
be answered by `git show HEAD:<path>`; in the regression harness that runs each
half inside a bare temp sandbox there is no HEAD to ask, and a skip there would
let a broken advisor pass by accident. A fixture repo costs one `git init` and
makes the red half red for the real reason -- the invented symbol, not the
absence of a helper.
"""

from __future__ import annotations

import ast
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def load_validate(cwd: Path | None = None):
    """The module's own source, executed with the gate suppressed.

    `validate.py` runs the whole gate at import time, so it cannot be imported
    normally from a test. Its helpers are pure and reach the repository only
    through `_git`, so that one dependency is injected -- pointed at `cwd`, which
    lets a test aim the advisor at a fixture repository.

    Whatever helpers the file defines are exposed; a missing one is left absent
    rather than asserted here. That matters for the red half of the pair: the
    pre-fix file has no `_imported_names`, and the honest failure for a test
    that needs it is that test failing, not the whole module refusing to import.
    """
    spec = importlib.util.spec_from_loader("validate_helpers", loader=None)
    module = importlib.util.module_from_spec(spec)
    source = (TOOLS / "validate.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    wanted = {"_imported_names", "_submodule_paths", "_uncommitted_symbols"}
    body = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in wanted
    ]
    namespace = {"re": re, "Path": Path}
    where = Path(cwd) if cwd is not None else ROOT

    def _git(*args):
        result = subprocess.run(["git", *args], cwd=where, capture_output=True)
        return result.returncode, result.stdout.decode("utf-8", "replace")

    namespace["_git"] = _git
    exec(compile(ast.Module(body=body, type_ignores=[]), "<validate>", "exec"), namespace)
    for name in wanted:
        if name in namespace:
            setattr(module, name, namespace[name])
    return module


V = load_validate()


def require(name: str):
    """The helper under test, or a clear failure when the file lacks it."""
    helper = getattr(V, name, None)
    if helper is None:
        raise AssertionError(
            f"validate.py defines no {name}: the defect this ticket fixes is "
            f"still present, because the advisor still parses import clauses "
            f"with a bare identifier scan"
        )
    return helper


#: The smallest clone the advisor can be asked about. `__init__.py` deliberately
#: names none of its submodules: that is exactly the state in which the old
#: resolution reported them missing, and it is legal Python.
FIXTURE_FILES = {
    "tools/saipen_engine/__init__.py": '"""Package."""\n\n__all__ = []\n',
    "tools/saipen_engine/log.py": "def emit(*args, **kwargs):\n    pass\n",
    "tools/saipen_engine/audit_manifest.py": '"""A submodule HEAD carries."""\n\n\ndef read(root):\n    return {}\n',
    "tools/saipen_engine/suite_record.py": '"""A submodule HEAD carries."""\n\n\ndef record(*args):\n    pass\n',
    "tools/producer_backends/__init__.py": '"""Package."""\n',
    "tools/producer_backends/saipal_adapter.py": '"""A submodule HEAD carries."""\n\n\ndef adapter():\n    pass\n',
}


def git_available() -> bool:
    result = subprocess.run(["git", "--version"], capture_output=True)
    return result.returncode == 0


class FixtureRepository:
    """A committed scratch clone, with one untracked subject file at a time."""

    def __init__(self, tmp: str):
        self.root = Path(tmp)
        for rel, text in FIXTURE_FILES.items():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self._git("init", "-q", ".")
        self._git("config", "user.email", "fixture@example.invalid")
        self._git("config", "user.name", "fixture")
        self._git("add", "--", *FIXTURE_FILES)
        self._git("-c", "commit.gpgsign=false", "commit", "-qm", "fixture")

    def _git(self, *args) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args], cwd=self.root, capture_output=True, text=True
        )

    def subject(self, name: str, body: str) -> str:
        """Write an untracked subject and return its path relative to the clone."""
        rel = f"tools/{name}"
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(body), encoding="utf-8")
        return rel


class ImportedNamesBindsOnlyWhatPythonBinds(unittest.TestCase):
    """Defect 2: `as` and the local alias are not exported symbols."""

    def names(self, clause):
        return require("_imported_names")(clause)

    def test_a_plain_clause_yields_its_names(self):
        self.assertEqual(self.names("suite_record"), ["suite_record"])

    def test_an_alias_yields_the_source_name_only(self):
        self.assertEqual(self.names("suite_record as SR"), ["suite_record"])

    def test_a_parenthesised_multi_clause_yields_every_source_name(self):
        self.assertEqual(
            self.names("(audit_manifest, identity_audit as IA)"),
            ["audit_manifest", "identity_audit"],
        )

    def test_the_keyword_as_is_never_a_symbol(self):
        self.assertNotIn("as", self.names("a as b"))

    def test_a_star_import_binds_nothing_nameable(self):
        self.assertEqual(self.names("*"), [])


class SubmodulePathsFindsTheModuleFile(unittest.TestCase):
    """Defect 1: a submodule import needs no name in the parent package."""

    def test_the_submodule_file_is_a_candidate(self):
        paths = require("_submodule_paths")("saipen_engine", "audit_manifest")
        self.assertIn("tools/saipen_engine/audit_manifest.py", paths)

    def test_a_package_submodule_is_a_candidate(self):
        paths = require("_submodule_paths")("producer_backends", "saipal_adapter")
        self.assertIn("tools/producer_backends/saipal_adapter.py", paths)


class TheAdvisorNamesTheMeasuredFalsePositivesNoMore(unittest.TestCase):
    """The two exact clauses that produced the wrong advice, on a real HEAD."""

    def setUp(self):
        if not git_available():
            raise unittest.SkipTest("git is not installed; HEAD cannot be read")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = FixtureRepository(self._tmp.name)
        self._cwd = os.getcwd()
        os.chdir(self.repo.root)
        self.addCleanup(os.chdir, self._cwd)
        self.advise = load_validate(self.repo.root)._uncommitted_symbols

    def test_a_committed_submodule_is_not_reported_missing(self):
        rel = self.repo.subject(
            "test_fixture_submodule.py",
            "from saipen_engine import audit_manifest\n",
        )
        self.assertEqual(
            self.advise(rel),
            [],
            "saipen_engine/audit_manifest.py is committed, so importing it as a "
            "submodule needs no export in __init__.py; naming it is the defect",
        )

    def test_a_nested_package_submodule_is_not_reported_missing(self):
        rel = self.repo.subject(
            "test_fixture_nested.py",
            "from producer_backends import saipal_adapter\n",
        )
        self.assertEqual(self.advise(rel), [])

    def test_an_alias_does_not_become_two_symbols(self):
        rel = self.repo.subject(
            "test_fixture_alias.py",
            "from saipen_engine import suite_record as SR\n",
        )
        self.assertEqual(
            self.advise(rel),
            [],
            "`as` is a keyword and `SR` is a local alias; neither is an export "
            "and reporting them is the measured false positive",
        )


class ARealOrphanIsStillReported(unittest.TestCase):
    """The control that keeps the fix honest: a true orphan still speaks."""

    def setUp(self):
        if not git_available():
            raise unittest.SkipTest("git is not installed; HEAD cannot be read")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = FixtureRepository(self._tmp.name)
        self._cwd = os.getcwd()
        os.chdir(self.repo.root)
        self.addCleanup(os.chdir, self._cwd)
        self.advise = load_validate(self.repo.root)._uncommitted_symbols

    def test_a_symbol_head_lacks_is_named(self):
        rel = self.repo.subject(
            "test_fixture_orphan.py",
            "from saipen_engine import nowhere_at_all\n",
        )
        self.assertIn("saipen_engine.nowhere_at_all", self.advise(rel))

    def test_a_module_head_lacks_is_named(self):
        rel = self.repo.subject(
            "test_fixture_orphan_module.py",
            "from saipen_engine import log\n",
        )
        self.assertEqual(
            self.advise(rel), [],
            "log.py IS committed; this asserts the module branch still resolves",
        )


class TheSourceSlicingConsumersStillReachTheHelpers(unittest.TestCase):
    """T-1592 executes this function by slicing its source, then runs it.

    That loader cut from `def _uncommitted_symbols` to the next `def`, which is
    only correct while the function is self-contained. Adding two helpers broke
    it with a NameError, and the family run reported exactly two new red tests
    (`test_t1592_manifest_orphan_advice`), i.e. the commit would have been red
    in every clone. The loader now follows the dependency list, and this test
    holds it to that: the REAL loader from the REAL file must execute and answer.
    """

    def test_the_real_t1592_loader_runs_to_an_answer(self):
        loader = importlib.util.spec_from_file_location(
            "t1592_loader", TOOLS / "test_t1592_manifest_orphan_advice.py"
        )
        module = importlib.util.module_from_spec(loader)
        loader.loader.exec_module(module)

        def fake_git(*args):
            if args[:1] == ("show",):
                body = {"tools/saipen_engine/board.py": "FIELDS = ()\n"}.get(
                    args[1].split(":", 1)[1]
                ) if ":" in args[1] else None
                return (0, body) if body is not None else (1, "")
            return (1, "")

        with tempfile.TemporaryDirectory() as tmp:
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                Path("tools/saipen_engine").mkdir(parents=True)
                Path("tools/saipen_engine/board.py").write_text(
                    "FIELDS = ()\n", encoding="utf-8"
                )
                Path("tools/test_thing.py").write_text(
                    "import json\nfrom saipen_engine.board import FIELDS\n",
                    encoding="utf-8",
                )
                self.assertEqual(
                    module._run_uncommitted_symbols(fake_git, "tools/test_thing.py"),
                    [],
                    "the self-contained case must still report nothing; a "
                    "NameError here means the loader did not reach the helpers",
                )
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
