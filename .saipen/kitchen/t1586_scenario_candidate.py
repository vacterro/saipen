import ast
import hashlib
import importlib.util
import io
import json
import sys
import types
import unittest
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "tools"))
out = root / ".saipen/evidence/T-1586-scenario-candidate"
out.mkdir(parents=True, exist_ok=True)
subjects = ["tools/run_scenarios.py", "tools/perf_wave_regressions.py"]
before = {rel: (root / rel).read_bytes() for rel in subjects}
run_text = before[subjects[0]].decode("utf-8")

def replace_once(text, old, new):
    if old not in text:
        old, new = old.replace("\n", "\r\n"), new.replace("\n", "\r\n")
    assert text.count(old) == 1, old[:80]
    return text.replace(old, new)

old = '''_IGNORE_RUNTIME = shutil.ignore_patterns(
    "__pycache__", "*.pyc", ".saipen/recovery", ".saipen/locks", ".saipen/cache"
)'''
new = '''def _without_probe_runtime(ignore):
    """A fixture gets its own ephemeral locks/cache; durable evidence stays."""
    def wrapped(directory, names):
        ignored = set(ignore(directory, names))
        if Path(directory).name == ".saipen":
            ignored.update(name for name in names if name in ("locks", "cache"))
        return ignored

    return wrapped


_IGNORE_RUNTIME = _without_probe_runtime(shutil.ignore_patterns("__pycache__", "*.pyc"))'''
run_text = replace_once(run_text, old, new)
# Wrap the actual live-home copy callbacks, retaining each existing ignore set.
lines = run_text.splitlines(keepends=True)
offsets = [0]
for line in lines:
    offsets.append(offsets[-1] + len(line))
replacements = []
for node in ast.walk(ast.parse(run_text)):
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "copytree" and node.args
            and isinstance(node.args[0], ast.Name) and node.args[0].id in ("HOME", "home")):
        continue
    keyword = next((kw for kw in node.keywords if kw.arg == "ignore"), None)
    assert keyword is not None
    value = keyword.value
    begin = offsets[value.lineno - 1] + value.col_offset
    end = offsets[value.end_lineno - 1] + value.end_col_offset
    # All modified callback expressions contain ASCII, so AST byte columns agree.
    expression = run_text[begin:end]
    assert expression.startswith("shutil.ignore_patterns(")
    replacements.append((begin, end, "_without_probe_runtime(" + expression + ")"))
for begin, end, updated in sorted(replacements, reverse=True):
    run_text = run_text[:begin] + updated + run_text[end:]
assert len(replacements) >= 2
run_text = replace_once(run_text,
    '            f"schema_version: 3\\nlast_event: {last_event}\\n"\n'
    '            f\'saipen_home: "{HOME.as_posix()}"\\nagent: probe\\nrequires:\\n  - filesystem\\n\'',
    '            f"schema_version: 3\\nlast_event: {last_event}\\n"\n'
    '            f"style_contract: {CURRENT_STYLE_CONTRACT}\\n"\n'
    '            f\'saipen_home: "{HOME.as_posix()}"\\nagent: probe\\nrequires:\\n  - filesystem\\n\'')
run_text = replace_once(run_text,
'''        expect(
            "generic role binds to its governing PROTOCOL digest",
            validate(project),
            absent=mismatch,
        )
        generic_protocol.write_text("generic contract v2\\n", encoding="utf-8")
        expect(
            "generic role contract change makes package stale", validate(project), contains=mismatch
        )''',
'''        # Arbitrary generic names are outside the fixed Core OUTBOX registry.
        # Exercise their shared freshness authority, used by sub operations;
        # the registered-producer validator controls above remain unchanged.
        from saipen_engine.subs import role_freshness

        expect(
            "generic role binds to its governing PROTOCOL digest",
            role_freshness(project, "saicustom", generic_revision),
            contains="current",
        )
        generic_protocol.write_text("generic contract v2\\n", encoding="utf-8")
        expect(
            "generic role contract change makes package stale",
            role_freshness(project, "saicustom", generic_revision),
            contains="stale",
        )''')
perf_text = before[subjects[1]].decode("utf-8")
old = '''    transient = ("cache/",)

    def tree_snapshot(path: Path) -> dict[str, str]:
        snapshot: dict[str, str] = {}
        for p in sorted(path.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(path).as_posix()
            if rel.startswith(transient):
                continue
            snapshot[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
        return snapshot

'''
perf_text = replace_once(perf_text, old, "")
snapshot = '''def probe_memory_snapshot(path: Path) -> dict[str, str]:
    """Read-only purity fingerprint of durable memory, without host runtime."""
    snapshot: dict[str, str] = {}
    for item in sorted(path.rglob("*")):
        rel = item.relative_to(path).as_posix()
        if rel.startswith(("cache/", "locks/")) or not item.is_file():
            continue
        snapshot[rel] = hashlib.sha256(item.read_bytes()).hexdigest()
    return snapshot


'''
assert perf_text.count('def run_t1022(') == 1
perf_text = perf_text.replace('def run_t1022(', snapshot + 'def run_t1022(')
assert perf_text.count('tree_snapshot(HOME / ".saipen")') == 2
perf_text = perf_text.replace('tree_snapshot(HOME / ".saipen")',
                              'probe_memory_snapshot(HOME / ".saipen")')
after = {subjects[0]: run_text.encode("utf-8"), subjects[1]: perf_text.encode("utf-8")}
tests = r'''"""T-1586: fixture inputs reach real gates and preserve durable memory."""
from __future__ import annotations

import ast
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
        for outer_name, inner_name in (("run_release_executor_probes", "build_fixture"),
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
'''
oracle_rel = "tools/test_t1586_scenario_inputs.py"
assert not (root / oracle_rel).exists()
oracle = tests.encode("utf-8")
for rel in subjects:
    (out / (Path(rel).name + ".before")).write_bytes(before[rel])
    (out / Path(rel).name).write_bytes(after[rel])
(out / Path(oracle_rel).name).write_bytes(oracle)
spec = importlib.util.spec_from_file_location("t1586_fixed_oracle", out / Path(oracle_rel).name)
test_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(test_module)
runs = {}
for variant, content in (("before", before), ("candidate", after)):
    for symbol, rel in zip(("R", "P"), subjects):
        name = "t1586_" + symbol + "_" + variant
        implementation = types.ModuleType(name)
        implementation.__file__ = str(root / rel)
        sys.modules[name] = implementation
        exec(compile(content[rel].decode("utf-8"), str(root / rel), "exec"), implementation.__dict__)
        implementation._test_subject_text = content[rel].decode("utf-8")
        setattr(test_module, symbol, implementation)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromModule(test_module)
    )
    (out / f"oracle-{variant}.txt").write_text(stream.getvalue(), encoding="utf-8")
    runs[variant] = {"ran": result.testsRun, "failures": len(result.failures),
                     "errors": len(result.errors), "ok": result.wasSuccessful()}
manifest = {"subjects": [{"path": rel, "before_sha256": hashlib.sha256(before[rel]).hexdigest(),
                           "after_sha256": hashlib.sha256(after[rel]).hexdigest()}
                          for rel in subjects], "oracle": {"path": oracle_rel,
                          "sha256": hashlib.sha256(oracle).hexdigest()},
            "live_copy_callbacks_wrapped": len(replacements), "runs": runs}
(out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps(manifest, indent=2))
sys.exit(0 if not runs["before"]["ok"] and runs["before"]["errors"] == 0
         and runs["candidate"]["ok"] else 1)
