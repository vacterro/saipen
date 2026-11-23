"""T-1753: the activation block's launcher line names a launcher that exists.

The global activation block carried one variable, `{{SAIPEN_HOME}}`, for two
different directories: the PROTOCOL directory an agent reads `BOOT.md` and
`STYLE.md` from, and the runtime root whose `bin/` holds the launcher. Both
injectors substitute the protocol directory, so on a source clone every host
instruction file printed `<clone>/saipen/bin/saipen` while the launcher is
`<clone>/bin/saipen`. A cold session that followed the line failed its first
command (exit 127), and the same line forbids searching for another path.

The launcher line now names `{{SAIPEN_ROOT}}`. No renderer chooses it: each
derives it from the home it already substitutes -- the injectors from the
parent they already compute, `autoinject` through `protocol_home_runtime_root`
-- and a block whose launcher root is not the runtime root of its own home
reads stale, so `saipen host repair` replaces what the old injector wrote.

Every launcher here is rendered by `bootstrap/cli_launcher.py` and runs a stub
engine that prints where it lives, so executing the printed line proves which
installation it reaches without starting a real SAIPEN.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
for _path in (TOOLS, REPO / "bootstrap"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import autoinject  # noqa: E402
import cli_launcher  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402


def setUpModule():
    # The injector run below redirects only USERPROFILE/HOME; an operator's
    # ZAICODE_HOME would otherwise receive a real install (T-1504).
    isolate_host_session()


TEMPLATE = REPO / "saipen" / "ACTIVATION_BLOCK.md"
PS1 = REPO / "bootstrap" / "inject.ps1"
SH = REPO / "bootstrap" / "inject.sh"
MARKER = "T1753-ENGINE"
#: The launcher sentence of the template, whatever the line breaks inside it.
LAUNCHER_LINE = re.compile(
    r"run `(?P<posix>[^`]+)`\s+\(POSIX,\s+Git\s+Bash\)\s+or\s+`(?P<cmd>[^`]+)`"
    r"\s+\(cmd,\s+PowerShell\)"
)

#: A fixture generation small enough to copy, as test_instruction_home_parity
#: builds it (T-1342): a home counts only when it proves this generation.
_MINI_MANIFEST = {
    "copy_trees": [{"src": "extensions/adapters", "dst": "extensions/adapters"}],
    "files": [
        {"src": "saipen/MANIFEST.json", "required": True},
        {"src": "saipen/BOOT.md", "required": True},
        {"src": "saipen/CORE.md", "required": True},
        {"src": "saipen/ACTIVATION_BLOCK.md", "required": True},
        {"src": "VERSION", "required": True},
    ],
}
_STUB_ENGINE = (
    "import sys\n"
    "from pathlib import Path\n"
    f"print({MARKER!r}, Path(__file__).resolve().parent.parent, *sys.argv[1:])\n"
)

_TEMP: list[tempfile.TemporaryDirectory] = []


def _tempdir(prefix: str) -> Path:
    tmp = tempfile.TemporaryDirectory(prefix=prefix)
    _TEMP.append(tmp)
    return Path(tmp.name)


def _engine_and_launchers(root: Path) -> None:
    """A stub `tools/saipen.py` and the launchers the installer renders for it."""
    (root / "tools").mkdir(parents=True, exist_ok=True)
    engine = root / "tools" / "saipen.py"
    engine.write_text(_STUB_ENGINE, encoding="utf-8")
    for path in cli_launcher.write_launchers(sys.executable, str(engine), root / "bin"):
        path.chmod(0o755)


def _clone(base: Path) -> Path:
    """A source-layout home: protocol documents in `saipen/`, `bin/` beside it."""
    (base / "saipen").mkdir(parents=True, exist_ok=True)
    (base / "saipen" / "MANIFEST.json").write_text(
        json.dumps(_MINI_MANIFEST, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (base / "saipen" / "BOOT.md").write_text("# BOOT\n", encoding="utf-8")
    (base / "saipen" / "CORE.md").write_text("# CORE\n", encoding="utf-8")
    (base / "saipen" / "ACTIVATION_BLOCK.md").write_bytes(TEMPLATE.read_bytes())
    (base / "VERSION").write_text("7.t\n", encoding="utf-8")
    (base / "extensions" / "adapters").mkdir(parents=True, exist_ok=True)
    (base / "extensions" / "adapters" / "registry.json").write_bytes(
        (REPO / "extensions" / "adapters" / "registry.json").read_bytes()
    )
    _engine_and_launchers(base)
    return base


def _installed(root: Path, clone: Path) -> Path:
    """A flattened installed home at the clone's generation, named like one."""
    root.mkdir(parents=True, exist_ok=True)
    for name in ("MANIFEST.json", "BOOT.md", "CORE.md", "ACTIVATION_BLOCK.md"):
        shutil.copyfile(clone / "saipen" / name, root / name)
    shutil.copyfile(clone / "VERSION", root / "VERSION")
    shutil.copytree(
        clone / "extensions" / "adapters", root / "extensions" / "adapters", dirs_exist_ok=True
    )
    _engine_and_launchers(root)
    return root


CLONE = _clone(_tempdir("saipen-t1753-clone-"))
PROTOCOL = CLONE / "saipen"
INSTALLED = _installed(_tempdir("saipen-t1753-profile-") / "skills" / "saipen", CLONE)


def _find_bash() -> str | None:
    """A working bash: on Windows a plain `bash` may be the WSL stub."""
    for candidate in (
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files (x86)\Git\bin\bash.exe",
        shutil.which("bash"),
    ):
        if candidate and os.path.exists(candidate) and "system32" not in candidate.lower():
            return candidate
    return None


def _find_powershell() -> str | None:
    for name in ("pwsh", "powershell"):
        found = shutil.which(name)
        if found:
            return found
    return None


BASH = _find_bash()
POWERSHELL = _find_powershell()


class ClonePatch:
    """`autoinject` answers for the fixture clone, as it does for a real one."""

    def setUp(self):
        super().setUp()
        patch = unittest.mock.patch.object(autoinject, "HOME", CLONE)
        patch.start()
        self.addCleanup(patch.stop)


def _launcher_paths(block: str) -> tuple[str, str]:
    match = LAUNCHER_LINE.search(block)
    assert match, "the block carries no launcher sentence"
    return match.group("posix"), match.group("cmd")


def _same(left: str | Path, right: str | Path) -> bool:
    try:
        return os.path.samefile(str(left), str(right))
    except OSError:
        return False


def _launched_root(stdout: str) -> str:
    line = next(line for line in stdout.splitlines() if line.startswith(MARKER))
    return line[len(MARKER) :].strip().rsplit(" ", 1)[0]


def _template_block() -> str:
    raw = autoinject.activation_template_path().read_text(encoding="utf-8")
    return autoinject._extract_block(raw).replace("\r\n", "\n").strip()


def _surface(block: str) -> dict:
    target = _tempdir("saipen-t1753-instr-") / "INSTR.md"
    target.write_text("# operator notes\n\n" + block + "\n\ntrailing text\n", encoding="utf-8")
    return {"instruction_surfaces": [str(target)]}


class LauncherLineTests(ClonePatch, unittest.TestCase):
    def test_a_clone_block_names_the_launcher_of_the_clone(self):
        posix, cmd = _launcher_paths(autoinject.rendered_activation_block(PROTOCOL))
        self.assertTrue(_same(posix, CLONE / "bin" / "saipen"), posix)
        self.assertTrue(_same(cmd, CLONE / "bin" / "saipen.cmd"), cmd)

    def test_an_installed_block_names_the_launcher_of_the_installation(self):
        posix, cmd = _launcher_paths(autoinject.rendered_activation_block(INSTALLED))
        self.assertTrue(_same(posix, INSTALLED / "bin" / "saipen"), posix)
        self.assertTrue(_same(cmd, INSTALLED / "bin" / "saipen.cmd"), cmd)

    def test_the_documents_still_come_from_the_protocol_directory(self):
        for home in (PROTOCOL, INSTALLED):
            block = autoinject.rendered_activation_block(home).replace("\\", "/")
            for name in ("BOOT.md", "STYLE.md", "UI.md"):
                self.assertIn(str(home).replace("\\", "/") + "/" + name, block)

    @unittest.skipUnless(BASH, "working bash runtime unavailable")
    def test_the_posix_line_runs_the_engine_of_the_home_it_names(self):
        for root, home in ((CLONE, PROTOCOL), (INSTALLED, INSTALLED)):
            posix, _ = _launcher_paths(autoinject.rendered_activation_block(home))
            ran = subprocess.run(
                [BASH, "-c", shlex.quote(posix) + " probe"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            self.assertEqual(ran.returncode, 0, f"{posix}: {ran.stdout}{ran.stderr}")
            self.assertTrue(_same(_launched_root(ran.stdout), root), ran.stdout)

    @unittest.skipUnless(os.name == "nt", "cmd.exe exists only on Windows")
    def test_the_cmd_line_runs_the_engine_of_the_home_it_names(self):
        for root, home in ((CLONE, PROTOCOL), (INSTALLED, INSTALLED)):
            _, cmd = _launcher_paths(autoinject.rendered_activation_block(home))
            ran = subprocess.run(
                ["cmd.exe", "/d", "/c", cmd, "probe"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            self.assertEqual(ran.returncode, 0, f"{cmd}: {ran.stdout}{ran.stderr}")
            self.assertTrue(_same(_launched_root(ran.stdout), root), ran.stdout)


class InstructionStatusTests(ClonePatch, unittest.TestCase):
    def test_both_spellings_of_the_home_read_current(self):
        for home in (PROTOCOL, INSTALLED):
            adapter = _surface(autoinject._extract_block(autoinject.rendered_activation_block(home)))
            self.assertEqual(autoinject.instruction_status(adapter, INSTALLED), "current", home)

    def test_the_launcher_under_the_protocol_directory_is_stale(self):
        """What the old injector wrote into every host on a source clone."""
        old = _template_block().replace("{{SAIPEN_HOME}}", str(PROTOCOL))
        old = old.replace("{{SAIPEN_ROOT}}", str(PROTOCOL))
        self.assertEqual(autoinject.instruction_status(_surface(old), INSTALLED), "stale")

    def test_the_same_substitution_is_right_for_an_installed_home(self):
        same = _template_block().replace("{{SAIPEN_HOME}}", str(INSTALLED))
        same = same.replace("{{SAIPEN_ROOT}}", str(INSTALLED))
        self.assertEqual(autoinject.instruction_status(_surface(same), INSTALLED), "current")

    def test_a_launcher_of_another_installation_is_stale(self):
        mixed = _template_block().replace("{{SAIPEN_HOME}}", str(PROTOCOL))
        mixed = mixed.replace("{{SAIPEN_ROOT}}", str(INSTALLED))
        self.assertEqual(autoinject.instruction_status(_surface(mixed), INSTALLED), "stale")


def _disposable_env(home: Path) -> dict[str, str]:
    """A child environment that can only write inside `home`."""
    env = dict(os.environ)
    env["USERPROFILE"] = str(home)
    env["HOME"] = str(home)
    env["SAIPEN_PYTHON"] = sys.executable
    for key in (
        "SAIPEN_PROJECT_ROOT",
        "SAIPEN_PROJECT_LINEAGE",
        "SAIPEN_AGENT",
        "SAIPEN_SKILL_ROOT",
        "CLAUDE_CONFIG_DIR",
    ):
        env.pop(key, None)
    return env


class InjectorTests(unittest.TestCase):
    """Both injectors print the launcher of the clone they run from."""

    def _block(self, home: Path) -> str:
        text = (home / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")
        match = re.search(r"<!-- SAIPEN:BEGIN -->.*?<!-- SAIPEN:END -->", text, re.DOTALL)
        self.assertIsNotNone(match, "no SAIPEN block in the installed instructions")
        return match.group(0)

    def _assert_launcher_of_this_clone(self, block: str, label: str) -> None:
        posix, cmd = _launcher_paths(block)
        for printed, expected in ((posix, "saipen"), (cmd, "saipen.cmd")):
            self.assertEqual(
                printed.replace("\\", "/").casefold(),
                str(REPO.resolve() / "bin" / expected).replace("\\", "/").casefold(),
                label,
            )

    @unittest.skipUnless(BASH, "working bash runtime unavailable")
    def test_the_posix_injector_names_the_launcher_of_its_clone(self):
        home = _tempdir("saipen-t1753-sh-home-")
        (home / ".claude").mkdir()
        env = _disposable_env(home)
        env["HOME"] = str(home).replace("\\", "/")
        ran = subprocess.run(
            [BASH, str(SH), "--adapter", "claude"],
            capture_output=True,
            text=True,
            env=env,
            timeout=600,
        )
        self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
        self._assert_launcher_of_this_clone(self._block(home), "inject.sh")

    @unittest.skipUnless(POWERSHELL and os.name == "nt", "Windows PowerShell unavailable")
    def test_the_windows_injector_names_the_launcher_of_its_clone(self):
        home = _tempdir("saipen-t1753-ps1-home-")
        (home / ".claude").mkdir()
        ran = subprocess.run(
            [
                POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                "-File", str(PS1), "-AdapterId", "claude",
            ],
            capture_output=True,
            text=True,
            env=_disposable_env(home),
            timeout=600,
        )
        self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
        self._assert_launcher_of_this_clone(self._block(home), "inject.ps1")


if __name__ == "__main__":
    unittest.main()
