"""T-1348: repository file identity without hijacking foreign module names."""

from __future__ import annotations

import subprocess
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from test_hermetic_env import hermetic_env

ROOT = Path(__file__).resolve().parents[1]


class ToolModuleIdentityTests(unittest.TestCase):
    def probe(self, code: str, cwd: Path = ROOT) -> None:
        result = subprocess.run(
            [sys.executable, "-B", "-c", code], cwd=cwd,
            env=hermetic_env(), capture_output=True, text=True,
            encoding="utf-8", timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def isolated_tools(self, directory: Path, module_source: str, state_source: str) -> None:
        tools = directory / "tools"
        tools.mkdir()
        helper = ROOT / "tools/_module_identity.py"
        if helper.exists():
            shutil.copyfile(helper, tools / "_module_identity.py")
        (tools / "__init__.py").write_text('''
import sys
from pathlib import Path
directory = Path(__file__).resolve().parent
sys.path.append(str(directory))
if (directory / '_module_identity.py').exists():
    from ._module_identity import install
    install(directory)
''', encoding="utf-8")
        (tools / "owned_probe.py").write_text(module_source, encoding="utf-8")
        (directory / "probe_state.py").write_text(state_source, encoding="utf-8")

    def test_flat_first_reuses_the_mutable_cli_object(self) -> None:
        self.probe("""
import importlib, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'tools'))
flat = importlib.import_module('saipen')
flat._AGENT_OVERRIDE = 't1348-seat'
dotted = importlib.import_module('tools.saipen')
assert flat is dotted, 'CLI file executed twice'
assert dotted._AGENT_OVERRIDE == 't1348-seat'
assert dotted.__spec__.name == flat.__name__
""")

    def test_dotted_first_reuses_the_mutable_cli_object(self) -> None:
        self.probe("""
import importlib, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'tools'))
dotted = importlib.import_module('tools.saipen')
dotted._AGENT_OVERRIDE = 't1348-seat'
flat = importlib.import_module('saipen')
assert flat is dotted, 'CLI file executed twice'
assert flat._AGENT_OVERRIDE == 't1348-seat'
assert flat.__spec__.name == dotted.__name__
assert importlib.reload(flat) is dotted
assert flat._AGENT_OVERRIDE is None, 'reload suppressed CLI source execution'
""")

    def test_flat_test_module_and_dotted_test_module_share_identity(self) -> None:
        self.probe("""
import importlib, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'tools'))
flat = importlib.import_module('test_hermetic_env')
dotted = importlib.import_module('tools.test_hermetic_env')
assert flat is dotted, 'test harness executed twice'
""")

    def test_flat_import_after_tools_binds_the_package_attribute(self) -> None:
        self.probe("""
import tools
import saipen
import tools.saipen
assert tools.saipen is saipen
from tools import saipen as from_package
assert from_package is saipen
""")

    def test_loaded_foreign_flat_module_is_preserved(self) -> None:
        self.probe("""
import importlib, sys, types
foreign = types.ModuleType('saipen')
foreign.__file__ = '/foreign/saipen.py'
sys.modules['saipen'] = foreign
dotted = importlib.import_module('tools.saipen')
assert importlib.import_module('saipen') is foreign
assert dotted is not foreign
assert dotted.__name__ == 'tools.saipen'
""")

    def test_unloaded_foreign_package_keeps_its_resolution(self) -> None:
        with tempfile.TemporaryDirectory(prefix="saipen-t1348-foreign-") as tmp:
            package = Path(tmp) / "saipen"
            package.mkdir()
            (package / "__init__.py").write_text("marker = 'foreign'\n", encoding="utf-8")
            self.probe(f"""
import importlib, sys
sys.path.insert(0, {tmp!r})
dotted = importlib.import_module('tools.saipen')
flat = importlib.import_module('saipen')
assert flat.marker == 'foreign'
assert flat is not dotted
""")

    def test_alias_loader_supports_runpy(self) -> None:
        self.probe("""
import importlib, runpy, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'tools'))
flat = importlib.import_module('protocol_budget')
alias = importlib.import_module('tools.protocol_budget')
assert alias is flat
values = runpy.run_module('tools.protocol_budget', run_name='t1348_non_main')
assert callable(values['load_profiles'])
assert alias.__spec__.name == flat.__name__
""")

    def test_failed_import_cleans_both_names_before_retry(self) -> None:
        with tempfile.TemporaryDirectory(prefix="saipen-t1348-failure-") as tmp:
            directory = Path(tmp)
            self.isolated_tools(directory, '''
import probe_state
probe_state.executions += 1
if probe_state.fail_once:
    probe_state.fail_once = False
    raise RuntimeError('known import failure')
ready = True
''', "executions = 0\nfail_once = True\n")
            self.probe('''
import importlib, sys, tools, probe_state
try:
    importlib.import_module('tools.owned_probe')
except RuntimeError:
    pass
else:
    raise AssertionError('negative import control did not fail')
assert 'tools.owned_probe' not in sys.modules
assert 'owned_probe' not in sys.modules
assert not hasattr(tools, 'owned_probe')
dotted = importlib.import_module('tools.owned_probe')
flat = importlib.import_module('owned_probe')
assert dotted is flat
assert flat.ready
assert probe_state.executions == 2
''', cwd=directory)

    def test_concurrent_alias_waits_for_the_same_initialized_object(self) -> None:
        with tempfile.TemporaryDirectory(prefix="saipen-t1348-threads-") as tmp:
            directory = Path(tmp)
            self.isolated_tools(directory, '''
import probe_state
probe_state.executions += 1
probe_state.started.set()
assert probe_state.release.wait(10)
ready = True
''', '''
from threading import Event
started = Event()
release = Event()
executions = 0
''')
            self.probe('''
import importlib, threading, tools, probe_state
outputs = {}
errors = []
second_started = threading.Event()
def load(name):
    try:
        if name.startswith('tools.'):
            second_started.set()
        module = importlib.import_module(name)
        outputs[name] = (module, getattr(module, 'ready', False))
    except BaseException as error:
        errors.append(str(error))
flat = threading.Thread(target=load, args=('owned_probe',))
alias = threading.Thread(target=load, args=('tools.owned_probe',))
flat.start()
try:
    assert probe_state.started.wait(5)
    alias.start()
    assert second_started.wait(5)
    alias.join(0.1)
finally:
    probe_state.release.set()
flat.join(10)
alias.join(10)
assert not flat.is_alive() and not alias.is_alive()
assert not errors, errors
assert outputs['owned_probe'][0] is outputs['tools.owned_probe'][0]
assert all(item[1] for item in outputs.values()), 'partly initialized alias escaped'
assert probe_state.executions == 1
''', cwd=directory)

    def test_reload_reexecutes_owned_source_once(self) -> None:
        with tempfile.TemporaryDirectory(prefix="saipen-t1348-reload-") as tmp:
            directory = Path(tmp)
            self.isolated_tools(directory, '''
import probe_state
probe_state.executions += 1
ready = True
''', "executions = 0\n")
            self.probe('''
import importlib, probe_state
dotted = importlib.import_module('tools.owned_probe')
flat = importlib.import_module('owned_probe')
assert flat is dotted
assert probe_state.executions == 1
assert importlib.reload(flat) is dotted
assert probe_state.executions == 2, 'reload must execute source exactly once'
assert importlib.reload(dotted) is flat
assert probe_state.executions == 3
''', cwd=directory)

    def test_script_and_module_entry_still_match(self) -> None:
        results = [subprocess.run(
            [sys.executable, "-B", *prefix, "--help"], cwd=ROOT,
            env=hermetic_env(), capture_output=True, text=True,
            encoding="utf-8", timeout=90,
        ) for prefix in (["tools/saipen.py"], ["-m", "tools.saipen"])]
        self.assertEqual(results[0].returncode, results[1].returncode)
        self.assertIn("usage: saipen", results[0].stdout)
        self.assertEqual(results[0].stdout, results[1].stdout)
        self.assertNotIn("get_code", results[1].stderr)


if __name__ == "__main__":
    unittest.main()
