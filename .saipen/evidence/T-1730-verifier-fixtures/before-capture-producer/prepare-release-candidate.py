"""Prepare the isolated harness candidate; never edit the live source here."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGET = ROOT / ".saipen/evidence/T-1726-closed-contracts/cache-candidate/tools/run_scenarios.py"
assert TARGET.resolve().is_relative_to(ROOT / ".saipen/evidence")
text = TARGET.read_text(encoding="utf-8")
saved = Path(__file__).with_name("candidate-before-native-release.py")
if not saved.exists():
    saved.write_text(text, encoding="utf-8")

helper = r'''def build_release_fixture(
    tmp: Path, *, mode: str = "full", gitless: bool = False, foreign: bool = False,
    stop_at_review: bool = False,
) -> tuple:
    """A real disposable consumer project driven by the installed engine.

    Release mechanics do not need the author's historical Work, opaque
    evidence or private runtime state. This project publishes a real utility
    source file and executes its own two-test contract. SAIPEN's own declared
    full-unit family remains binding on projects that actually declare it.
    """
    from saipen_engine.paths import unbound_environment

    tmp = Path(tmp).resolve()
    if not tmp.is_relative_to(Path(tempfile.gettempdir()).resolve()):
        raise ValueError("release fixture must be inside the disposable temp root")
    project = tmp / "home"
    project.mkdir()
    env = {
        **unbound_environment(), "SAIPEN_CAPABILITY": mode,
        "GIT_AUTHOR_NAME": "probe", "GIT_AUTHOR_EMAIL": "probe@example.invalid",
        "GIT_COMMITTER_NAME": "probe", "GIT_COMMITTER_EMAIL": "probe@example.invalid",
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
    }
    source = project / "tools/saipen_engine/release_contract.py"
    source.parent.mkdir(parents=True)
    shutil.copyfile(HOME / "tools/saipen_engine/release_contract.py", source)
    launcher = project / "tools/saipen.py"
    launcher.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(HOME / 'tools')!r})\n"
        "from saipen import main\n"
        "raise SystemExit(main())\n", encoding="utf-8",
    )
    old_ver = (HOME / "VERSION").read_text(encoding="utf-8").strip()
    major, minor, patch = old_ver.split(".")
    new_ver = f"{major}.{minor}.{int(patch) + 1}"
    (project / "VERSION").write_text(old_ver + "\n", encoding="utf-8")
    for name in ("README.md", "README.ee.md", "README.ded.md", "README.ja.md"):
        (project / name).write_text(f"# Release fixture\n\n**v{old_ver}**\n", encoding="utf-8")
    (project / "CHANGELOG.md").write_text(f"## {old_ver}\n\nBaseline.\n", encoding="utf-8")
    (project / ".gitattributes").write_text("* -text\n", encoding="utf-8")
    (project / "tests").mkdir()
    (project / "tests/test_payload.py").write_text(
        "import importlib.util\nimport unittest\nfrom pathlib import Path\n"
        "ROOT = Path(__file__).resolve().parents[1]\n"
        "SPEC = importlib.util.spec_from_file_location('payload', "
        "ROOT / 'tools/saipen_engine/release_contract.py')\n"
        "PAYLOAD = importlib.util.module_from_spec(SPEC)\nSPEC.loader.exec_module(PAYLOAD)\n"
        "class Payload(unittest.TestCase):\n"
        "    def test_release_badge_matches_version(self):\n"
        "        version = (ROOT / 'VERSION').read_text().strip()\n"
        "        self.assertEqual(PAYLOAD.version_badges(ROOT / 'README.md'), [f'**v{version}**'])\n"
        "    def test_owned_source_marker_is_present(self):\n"
        "        self.assertIn('version_badges_owned(path)', "
        "(ROOT / 'tools/saipen_engine/release_contract.py').read_text())\n",
        encoding="utf-8",
    )

    def git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", "-C", str(project), *args], env=env,
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=120)

    def cli(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(launcher), "--project-root", str(project),
             "--agent", "probe", *args], cwd=project, env=env,
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
        )

    def admitted(*args: str) -> dict:
        result = cli(*args, "--json")
        try:
            body = json.loads(result.stdout)
        except ValueError as error:
            raise RuntimeError(f"fixture {args[0]} did not return JSON: {result.stderr[-500:]}") from error
        if result.returncode or not body.get("ok"):
            raise RuntimeError(f"fixture {' '.join(args[:2])} refused: {body}")
        return body

    admitted("init")
    admitted("transition", "PLAN")
    added = admitted("ticket", "add", "P1", "publish the reviewed fixture utility",
                     "--verify", "python -B -m unittest discover -s tests passes two payload tests")
    ticket = added["ticket"]
    admitted("claim", ticket)
    admitted("transition", "BUILD", ticket, "prepare reviewed fixture source")
    origin = tmp / "origin.git"
    if not gitless:
        for args in (("init", "-q"), ("config", "core.longpaths", "true"),
                     ("config", "core.autocrlf", "false"),
                     ("config", "core.hooksPath", ".git/hooks"),
                     ("add", "-A"), ("commit", "-qm", "probe: canonical BUILD baseline"),
                     ("branch", "-M", "main")):
            result = git(*args)
            if result.returncode:
                raise RuntimeError(f"fixture Git {args}: {result.stderr[-500:]}")
        subprocess.run(["git", "init", "-q", "--bare", str(origin)], env=env,
                       check=True, capture_output=True, timeout=120)
        git("remote", "add", "origin", origin.as_uri())
        result = git("push", "-q", "origin", "HEAD:main")
        if result.returncode:
            raise RuntimeError("fixture baseline push failed: " + result.stderr[-500:])
        subprocess.run(["git", "-C", str(origin), "symbolic-ref", "HEAD", "refs/heads/main"],
                       env=env, check=True, capture_output=True, timeout=120)
    else:
        origin.mkdir()

    source.write_text(source.read_text(encoding="utf-8").replace(
        "version_badges(path)", "version_badges_owned(path)"), encoding="utf-8")
    (project / "VERSION").write_text(new_ver + "\n", encoding="utf-8")
    for name in ("README.md", "README.ee.md", "README.ded.md", "README.ja.md"):
        path = project / name
        path.write_text(path.read_text(encoding="utf-8").replace(old_ver, new_ver), encoding="utf-8")
    changelog = project / "CHANGELOG.md"
    changelog.write_text(f"## {new_ver}\n\nTest release.\n\n" + changelog.read_text(encoding="utf-8"),
                         encoding="utf-8")
    if foreign:
        (project / "tools/foreign_file.py").write_text("FOREIGN = True\n", encoding="utf-8")
    admitted("transition", "VERIFY", ticket, "execute fixture payload contract")
    checked = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests"],
                             cwd=project, env=env, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=60)
    if checked.returncode or "Ran 2 tests" not in checked.stderr or "\nOK" not in checked.stderr:
        raise RuntimeError("fixture payload tests failed: " + checked.stderr[-1000:])
    admitted("checkpoint", "RUN", ticket, "verify -> PASS conf: high two executable payload tests")
    admitted("transition", "REVIEW", ticket, "fixture review accepted")
    if not stop_at_review:
        admitted("transition", "SHIP", ticket, "fixture release matrix")
        admitted("scope", ticket, "tools/saipen_engine/release_contract.py")
    return project, origin, git, cli, new_ver


'''

begin = text.index("def run_release_executor_probes()")
end = text.index("\n    def remote_branch_tip(", begin)
prefix = text[begin:end]
keep = prefix[:prefix.index("    def _cut_log(")]
replacement = '''    fixture_ticket = None

    def build_fixture(tmp: Path, *, mode="full", gitless=False, foreign=False):
        nonlocal fixture_ticket
        built = build_release_fixture(tmp, mode=mode, gitless=gitless, foreign=foreign)
        fixture_ticket = parse_state(codec.read_doc(built[0] / ".saipen/STATE.md"))["task"]
        return built
'''
text = text[:begin] + helper + keep + replacement + text[end:]
begin = text.index("def run_release_executor_probes()")
end = text.index("\ndef ", begin + 1)
section = text[begin:end]
section = section.replace('"- [x] T-9000"', 'f"- [x] {fixture_ticket}"')
section = section.replace('"T-9000.json"', 'f"{fixture_ticket}.json"')
section = section.replace('".saipen/kitchen/release_scope/T-9000.json"',
                          'f".saipen/kitchen/release_scope/{fixture_ticket}.json"')
section = section.replace('"T-9000"', 'fixture_ticket')
text = text[:begin] + section + text[end:]
assert "def _cut_log(" not in text and "def _append_fixture_verification(" not in text
TARGET.write_text(text, encoding="utf-8")
print("prepared isolated native release fixture candidate")
