"""T-1586: fixture inputs reach real gates and preserve durable memory."""
from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import perf_wave_regressions as P  # noqa: E402
import run_scenarios as R  # noqa: E402
from saipen_engine import codec  # noqa: E402
from saipen_engine.lock import project_writer_lock  # noqa: E402
from saipen_engine.operations import apply_claim, transition_phase  # noqa: E402
from saipen_engine.paths import unbound_environment  # noqa: E402
from saipen_engine.state import parse_state  # noqa: E402
from saipen_engine.subs import outbox_paths  # noqa: E402


def source_tree(module):
    return ast.parse(module._test_subject_text)


def named_function(module, name):
    return next(n for n in source_tree(module).body
                if isinstance(n, ast.FunctionDef) and n.name == name)


def nested_function(module, outer_name, inner_name):
    outer = named_function(module, outer_name)
    node = next(n for n in outer.body if isinstance(n, ast.FunctionDef) and n.name == inner_name)
    namespace = dict(module.__dict__)
    exec(compile(ast.Module(body=[node], type_ignores=[]), module.__file__, "exec"), namespace)
    return namespace[inner_name]


class ScenarioInputTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="saipen-scenario-inputs-")
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        for module in (R, P):
            if not hasattr(module, "_test_subject_text"):
                module._test_subject_text = Path(module.__file__).read_text(encoding="utf-8")

    def goal_fixture(self):
        make_project = nested_function(R, "run_nitro_m3_probes", "make_project")
        real_mkdtemp = tempfile.mkdtemp
        with mock.patch.object(R.tempfile, "mkdtemp",
                               side_effect=lambda **kw: real_mkdtemp(dir=self.base, **kw)):
            return make_project()

    def test_actual_goal_fixture_admits_claim_and_build_with_current_style(self):
        project = self.goal_fixture()
        claim = apply_claim(project, "T-1", "probe")
        self.assertTrue(claim.ok, claim.to_dict())
        built = transition_phase(project, "BUILD", "probe", "T-1", "fixture BUILD")
        self.assertTrue(built.ok, built.to_dict())
        state = parse_state(codec.read_doc(project / ".saipen/STATE.md"))
        self.assertEqual((state["phase"], state["task"]), ("BUILD", "T-1"))

    def test_missing_style_control_still_refuses_the_same_canonical_writer(self):
        project = self.goal_fixture()
        path = project / ".saipen/STATE.md"
        text = path.read_text(encoding="utf-8")
        path.write_text("\n".join(line for line in text.splitlines()
                                  if not line.startswith("style_contract:")) + "\n",
                        encoding="utf-8")
        result = apply_claim(project, "T-1", "probe")
        self.assertFalse(result.ok)
        self.assertIn("style_contract", result.message)

    def copy_callbacks(self):
        for outer_name, inner_name in (("run_t1012_strict_grammar_probes", None),
                                       ("run_nitro_probes", None)):
            outer = named_function(R, outer_name)
            if inner_name:
                outer = next(n for n in outer.body
                             if isinstance(n, ast.FunctionDef) and n.name == inner_name)
            call = next(n for n in ast.walk(outer)
                        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                        and n.func.attr == "copytree")
            expression = next(kw.value for kw in call.keywords if kw.arg == "ignore")
            yield eval(compile(ast.Expression(expression), R.__file__, "eval"), R.__dict__)

    def test_actual_copy_callbacks_skip_held_locks_but_preserve_durable_and_foreign_names(self):
        source = self.base / "source"
        for rel in (".saipen/evidence/proof.txt", ".saipen/cache/transient.txt",
                    "src/cache/owned.txt", "src/locks/owned.txt"):
            path = source / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"original\n")
        with project_writer_lock(source):
            for index, ignore in enumerate(self.copy_callbacks()):
                destination = self.base / f"copy-{index}"
                try:
                    shutil.copytree(source, destination, ignore=ignore)
                    error = None
                except (OSError, shutil.Error) as failure:
                    error = str(failure)
                self.assertIsNone(error, error)
                self.assertFalse((destination / ".saipen/locks").exists())
                self.assertFalse((destination / ".saipen/cache").exists())
                for rel in (".saipen/evidence/proof.txt", "src/cache/owned.txt",
                            "src/locks/owned.txt"):
                    self.assertEqual((destination / rel).read_bytes(), b"original\n")

    def snapshot(self):
        if hasattr(P, "probe_memory_snapshot"):
            return P.probe_memory_snapshot
        outer = named_function(P, "run_t1022")
        node = next(n for n in outer.body if isinstance(n, ast.FunctionDef)
                    and n.name == "tree_snapshot")
        assignment = next(n for n in outer.body if isinstance(n, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == "transient"
                                  for t in n.targets))
        namespace = dict(P.__dict__)
        exec(compile(ast.Module(body=[assignment, node], type_ignores=[]), P.__file__, "exec"),
             namespace)
        return namespace["tree_snapshot"]

    def memory_tree(self):
        root = self.base / "memory"
        for rel in ("evidence/proof.txt", "locks/core.lock", "cache/transient.txt",
                    "nested/locks/durable.txt"):
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"original\n")
        return root

    def test_purity_snapshot_excludes_runtime_but_retains_durable_nested_names(self):
        memory = self.memory_tree()
        result = self.snapshot()(memory)
        self.assertEqual(set(result), {"evidence/proof.txt", "nested/locks/durable.txt"})

    def test_purity_snapshot_still_refuses_unreadable_durable_evidence(self):
        memory = self.memory_tree()
        original_read = Path.read_bytes

        def read(path):
            if path == memory / "evidence/proof.txt":
                raise PermissionError("durable proof unreadable")
            return original_read(path)

        unreadable = mock.patch.object(Path, "read_bytes", read)
        refusal = self.assertRaisesRegex(PermissionError, "durable proof unreadable")
        with unreadable, refusal:
            self.snapshot()(memory)

    def generic_controls(self, *, stuck_current=False):
        outer = named_function(R, "run_role_freshness_probes")
        context = next(n for n in outer.body if isinstance(n, ast.With))
        begin = next(index for index, node in enumerate(context.body)
                     if isinstance(node, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == "generic_protocol"
                             for t in node.targets))
        end = next(index for index in range(begin, len(context.body))
                   if isinstance(context.body[index], ast.Expr)
                   and isinstance(context.body[index].value, ast.Call)
                   and ast.unparse(context.body[index].value.func) == "generic_protocol.unlink")
        project = self.base / "generic"
        outbox = project / ".saipen/extensions/subs/saiwiki/kitchen/OUTBOX.md"
        outbox.parent.mkdir(parents=True)
        outbox.write_text("## WIKI-900: fixture\n- **producer:** saiwiki\n"
                          "- **role_revision:** original-revision\n", encoding="utf-8")
        errors, seen = [], []

        def expect(label, output, contains="", absent=""):
            seen.append(label)
            if (contains and contains not in output) or (absent and absent in output):
                errors.append((label, output))

        # The old full validator does not discover arbitrary saicustom OUTBOX.
        # This records that actual registry boundary; it is not an accepted PASS.
        def validate(root):
            if any("saicustom" in str(path) for path in outbox_paths(root)):
                return "unexpected"
            return ""

        namespace = {**R.__dict__, "project": project, "rev2": "original-revision",
                     "expect": expect, "validate": validate,
                     "mismatch": "produced under a superseded role"}
        if stuck_current:
            guard = mock.patch("saipen_engine.subs.role_freshness", return_value="current")
        else:
            from contextlib import nullcontext
            guard = nullcontext()
        with guard:
            exec(compile(ast.Module(body=context.body[begin:end + 1], type_ignores=[]),
                         R.__file__, "exec"), namespace)
        self.assertEqual(len(seen), 2)
        return errors

    def test_generic_probe_uses_its_actual_freshness_authority(self):
        self.assertEqual(self.generic_controls(), [])

    def test_generic_known_bad_revision_still_fails_a_stuck_current_instrument(self):
        self.assertTrue(self.generic_controls(stuck_current=True))


def source_runtime_fixture(source: Path, destination: Path):
    """Copy declared public runtime inputs, then create native fixture history."""
    from saipen_engine.test_runner import _ignore_copy

    manifest = json.loads((source / "saipen/MANIFEST.json").read_text(encoding="utf-8"))
    destination.mkdir()
    for item in manifest["copy_trees"]:
        relative = item["src"]
        if Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise AssertionError("fixture refuses an unsafe runtime manifest path")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source / relative, target, ignore=_ignore_copy)
    for item in manifest["files"]:
        relative = item["src"]
        if Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise AssertionError("fixture refuses an unsafe runtime manifest path")
        path = source / relative
        if path.is_file():
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
    for relative in (".github", "tests"):
        if (source / relative).is_dir():
            shutil.copytree(source / relative, destination / relative,
                            ignore=_ignore_copy, dirs_exist_ok=True)
    for relative in (".gitignore", ".gitattributes", "README.md", "README.ee.md",
                     "README.ded.md", "README.ja.md", "CHANGELOG.md", "ruff.toml"):
        if (source / relative).is_file():
            shutil.copyfile(source / relative, destination / relative)
    env = {**unbound_environment(), "SAIPEN_USER_CONFIG_HOME": str(destination / "user-config")}
    for args in (("init",), ("ticket", "add", "P1", "native fixture seed",
                             "--verify", "the fixture remains canonical")):
        result = R.subprocess.run(
            [sys.executable, str(destination / "tools/saipen.py"), "--project-root",
             str(destination), "--agent", "probe", *args, "--json"],
            cwd=destination, env=env, capture_output=True, text=True, encoding="utf-8", timeout=120,
        )
        body = json.loads(result.stdout)
        if result.returncode or not body.get("ok"):
            raise AssertionError(body)


class NativeReleaseFixtureTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="saipen-native-release-inputs-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.source = self.base / "runtime"
        source_runtime_fixture(R.HOME, self.source)
        self.environment = mock.patch.dict(
            os.environ, {**unbound_environment(),
                         "SAIPEN_USER_CONFIG_HOME": str(self.base / "user-config")}, clear=True,
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        for name, value in (("HOME", self.source),
                            ("VALIDATOR", self.source / "tools/validate.py")):
            patched = mock.patch.object(R, name, value)
            patched.start()
            self.addCleanup(patched.stop)

    def builder(self):
        # Execute the actual nested builder on both old and corrected subjects.
        # Keeping the old closure prevents a missing new helper from being the
        # sole red control: the old fixture reaches the real admission refusal.
        R._test_subject_text = Path(R.__file__).read_text(encoding="utf-8")
        node = copy.deepcopy(named_function(R, "run_release_executor_probes"))
        first_case = next(index for index, statement in enumerate(node.body)
                          if isinstance(statement, ast.With))
        node.body = [*node.body[:first_case], ast.Return(value=ast.Name(
            id="build_fixture", ctx=ast.Load()))]
        node.name = "actual_fixture_builder"
        namespace = dict(R.__dict__)
        module = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
        exec(compile(module, R.__file__, "exec"), namespace)
        return namespace[node.name]()

    def test_real_release_fixture_reaches_ship_with_backed_history(self):
        from saipen_engine import lifecycle_authority
        from saipen_engine.log import parse_log_line

        slot = self.base / "positive"
        slot.mkdir()
        project, _origin, _git, cli, _version = self.builder()(slot)
        state = parse_state(codec.read_doc(project / ".saipen/STATE.md"))
        self.assertEqual(state["phase"], "SHIP")
        events = list(filter(None, map(parse_log_line,
                      (project / ".saipen/LOG.md").read_text(encoding="utf-8").splitlines())))
        floor, unbacked = lifecycle_authority.journal_floor(project, events)
        self.assertFalse(unbacked, unbacked)
        self.assertEqual(state["last_event"], floor)
        result = cli("ship", "--dry-run", "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["ok"])

    def test_declaring_core_family_still_requires_executed_evidence(self):
        slot = self.base / "declared"
        slot.mkdir()
        project, _origin, _git, cli, _version = R.build_release_fixture(
            slot, stop_at_review=True)
        declaration = project / "tools/saipen_engine/test_runner.py"
        declaration.write_bytes((self.source / "tools/saipen_engine/test_runner.py").read_bytes())
        state_path = project / ".saipen/STATE.md"
        before = state_path.read_bytes()
        state = parse_state(codec.read_doc(state_path))
        result = cli("transition", "SHIP", state["task"], "--json")
        body = json.loads(result.stdout)
        self.assertNotEqual(result.returncode, 0, body)
        self.assertEqual(body["code"], "INCOMPLETE_TICKET", body)
        self.assertIn("core_unit", body["canonical_next_command"])
        self.assertEqual(state_path.read_bytes(), before)

    def test_crlf_fixture_policy_still_rejects_actual_trailing_spaces(self):
        slot = self.base / "whitespace"
        slot.mkdir()
        project, _origin, git, _cli, _version = self.builder()(slot)
        (project / "space-control.txt").write_bytes(b"real trailing space \r\n")
        self.assertEqual(git("add", "--", "space-control.txt").returncode, 0)
        result = git("diff", "--cached", "--check")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("trailing whitespace", result.stdout + result.stderr)


class InstallerPreservationOracleTests(unittest.TestCase):
    def probe(self, *, lose_unowned=False):
        spec = importlib.util.spec_from_file_location(
            "fixture_install_ownership", ROOT / "bootstrap/install_ownership.py")
        ownership = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ownership)
        with tempfile.TemporaryDirectory(prefix="saipen-installer-oracle-") as directory:
            home = Path(directory)
            destination = home / ".claude/skills/saipen"
            config = home / ".claude/CLAUDE.md"
            aider = home / ".aider.conf.yml"

            def run(command, **kwargs):
                if command == ["install"]:
                    ledger = {"schema_version": 1, "files": {
                        path.relative_to(destination).as_posix(): hashlib.sha256(
                            path.read_bytes()).hexdigest()
                        for path in destination.rglob("*") if path.is_file()
                    }}
                    (destination / ownership.LEDGER).write_text(
                        json.dumps(ledger), encoding="utf-8")
                    (destination / "operator-data.txt").write_bytes(b"preserve unowned data\n")
                    config.write_bytes(R.ROUND_TRIP_BYTES + b"\n<!-- SAIPEN:BEGIN -->\n")
                    aider.write_bytes(R.AIDER_ROUND_TRIP_BYTES
                                      + b"\n# saipen protocol auto-loaded\nBOOT.md STYLE.md\n")
                elif command == ["uninstall"]:
                    # Exercise the real ownership remover. Only bootstrap
                    # process/config transport is doubled; full native shell
                    # integration is covered by the executable probe family.
                    ownership.remove(destination)
                    if lose_unowned:
                        (destination / "operator-data.txt").unlink()
                    config.write_bytes(R.ROUND_TRIP_BYTES)
                    aider.write_bytes(R.AIDER_ROUND_TRIP_BYTES + R.AIDER_SUFFIX_BYTES)
                else:
                    project = home / "validator-project"
                    return R.subprocess.CompletedProcess(
                        command, 0, f"Project root: {project.resolve()} (explicit)\n", "")
                return R.subprocess.CompletedProcess(command, 0, "Done.\n", "")

            with mock.patch.object(R, "installed_layout_problems", return_value=[]), \
                    mock.patch.object(R.subprocess, "run", side_effect=run):
                problem = R.run_injector_probe(
                    "ownership oracle", ["install"], ["uninstall"], {}, home)
            if not lose_unowned:
                self.assertEqual((destination / "operator-data.txt").read_bytes(),
                                 b"preserve unowned data\n")
            return problem

    def test_preserving_unowned_bytes_is_a_valid_uninstall(self):
        self.assertIsNone(self.probe())

    def test_unowned_data_loss_still_reddens_the_oracle(self):
        self.assertIn("changed preserved files", self.probe(lose_unowned=True))
