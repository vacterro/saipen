"""T-1427: instruction freshness must follow each LOADER's contract.

`instruction_status` used to answer from the FIRST declared surface that
happened to be current. In 2026-09 FreeBuff shipped two loaders with different
HOME knowledge contracts, and the registry declares both surfaces, so a home
carrying only `~/.knowledge.md` read `current` while FreeBuff Desktop -- which
then scanned the home for dot-prefixed entries and read the FIRST of
`.AGENTS.md`, `.CLAUDE.md` -- delivered nothing into the first-turn prompt.
That is the exact shape of the T-1426 live RED: the freshness surface said
the install was fine while a fresh desktop session had zero `cc` semantics.
(The desktop has since moved to the project root; see below. The defect class
T-1427 named -- a verdict computed from a surface its loader does not read --
is what this module still enforces.)

The measured loader contracts (from the hosts' own code; see
`test_host_bootstrap.FREEBUFF_CLI_HOME_SURFACES`):

  * freebuff CLI 0.2.34 (`~/.config/manicode/freebuff.exe`): scans the home for
    DOT-prefixed entries, matches the stripped name against
    `["agents.md","claude.md"]` case-insensitively, and reads the FIRST one it
    finds in that order -- so `.AGENTS.md`, then `.CLAUDE.md`. `~/.knowledge.md`
    is NOT a home surface for it: the only `*.knowledge.md` rule in that binary
    is a PROJECT-file predicate;
  * FreeBuff Desktop (2026-10-29 orchestrator): a PROJECT-root reader
    (`loadClaudeProjectInstructions(cwd)`, gated on `turn.projectInstructions`);
    it has no home surface at all.

The contract enforced here: an adapter declaring `instruction_loaders` is
current only when EVERY home-scoped loader DELIVERS the current block, and a
loader that delivers nothing makes the verdict stale with a diagnostic that
names the loader and the surface it reads. A loader declaring
`scope: project` is reported `not-applicable` -- a home verdict cannot measure
it, and the project half belongs to `saipen_engine.project_block` (T-1957).
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import autoinject  # noqa: E402

_TEMP: list[tempfile.TemporaryDirectory] = []

#: The pinned pre-fix `tools/autoinject.py` blob whose `instruction_status`
#: returned `current` from the first current surface in any order. It is the
#: red control for the loader-contract rule: the SAME fixture must be `stale`
#: under the fixed owner and was `current` under the pre-fix subject.
_PREFIX_AUTOINJECT_BLOB = "98dd6e7793d70bac725e8060aaf603047c4db167"

#: Case-sensitive names, in loader order, exactly as the hosts read them.
#: T-1957 re-measured the CLI out of `freebuff.exe` 0.2.34: `.knowledge.md` is
#: gone from the home contract (it is a project-file name there) and the order
#: is `.AGENTS.md` then `.CLAUDE.md`.
CLI_SURFACES = (".AGENTS.md", ".CLAUDE.md")
DESKTOP_SURFACES = ()

#: The FreeBuff Desktop loader's real surface is the PROJECT root (T-1957).
PROJECT_SURFACES = ("AGENTS.md", "CLAUDE.md", ".claude/CLAUDE.md")

#: T-1342: the accepted generation is the manifest-declared shipped runtime
#: surface, so a fixture carries its own small manifest.
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


def _tempdir(prefix: str) -> Path:
    tmp = tempfile.TemporaryDirectory(prefix=prefix)
    _TEMP.append(tmp)
    return Path(tmp.name)


def _authority(base: Path) -> Path:
    """A source-layout authority that answers every autoinject lookup."""
    (base / "saipen").mkdir(parents=True, exist_ok=True)
    (base / "saipen" / "MANIFEST.json").write_text(
        json.dumps(_MINI_MANIFEST, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (base / "saipen" / "BOOT.md").write_text("# BOOT\n", encoding="utf-8")
    (base / "saipen" / "CORE.md").write_text("# CORE\n", encoding="utf-8")
    (base / "saipen" / "ACTIVATION_BLOCK.md").write_bytes(
        (REPO / "saipen" / "ACTIVATION_BLOCK.md").read_bytes()
    )
    (base / "VERSION").write_text("7.t\n", encoding="utf-8")
    (base / "extensions" / "adapters").mkdir(parents=True, exist_ok=True)
    (base / "extensions" / "adapters" / "registry.json").write_bytes(
        (REPO / "extensions" / "adapters" / "registry.json").read_bytes()
    )
    return base


AUTHORITY = _authority(_tempdir("saipen-loader-authority-"))


class AuthorityPatch(unittest.TestCase):
    def setUp(self):
        super().setUp()
        patch = unittest.mock.patch.object(autoinject, "HOME", AUTHORITY)
        patch.start()
        self.addCleanup(patch.stop)


def _home(root: Path) -> Path:
    """A flattened installed home at the SAME accepted generation."""
    root.mkdir(parents=True, exist_ok=True)
    for name in ("MANIFEST.json", "BOOT.md", "CORE.md", "ACTIVATION_BLOCK.md", "VERSION"):
        source = AUTHORITY / "saipen" / name if name != "VERSION" else AUTHORITY / name
        if source.is_file():
            shutil.copyfile(source, root / name)
    shutil.copytree(
        AUTHORITY / "extensions" / "adapters",
        root / "extensions" / "adapters",
        dirs_exist_ok=True,
    )
    return root


def _block_for(skill: Path) -> str:
    return autoinject.rendered_activation_block(skill)


def _fixture(root: Path) -> tuple[Path, dict]:
    """A FreeBuff-shaped fixture home + the adapter entry it reports under.

    The surfaces are ABSOLUTE fixture paths with the same names and order the
    registry declares, so the test exercises the loader-contract logic without
    touching the real user home.
    """
    skill = _home(root / "skill")
    home = root / "home"
    home.mkdir(parents=True, exist_ok=True)
    surfaces = {
        ".knowledge.md": home / ".knowledge.md",
        ".AGENTS.md": home / ".AGENTS.md",
        ".claude.md": home / ".claude.md",
        ".CLAUDE.md": home / ".CLAUDE.md",
    }
    adapter = {
        "id": "freebuff",
        "instruction_surfaces": [
            str(surfaces[".knowledge.md"]),
            str(surfaces[".AGENTS.md"]),
        ],
        "instruction_loaders": [
            {
                "name": "freebuff CLI",
                "scope": "home",
                "surfaces": [str(surfaces[name]) for name in CLI_SURFACES],
            },
            {
                "name": "FreeBuff Desktop",
                "scope": "project",
                "surfaces": [str(surfaces[name]) for name in DESKTOP_SURFACES],
                "project_surfaces": [str(home / name) for name in PROJECT_SURFACES],
            },
        ],
        "freshness_surfaces": ["skill", "instruction"],
    }
    return skill, {"adapter": adapter, "surfaces": surfaces}


def _load_pre_fix_module():
    """The pinned pre-fix autoinject subject, or None when unprovable.

    The blob is materialised inside the authority fixture (`<AUTHORITY>/tools/`)
    so the module's own `HOME` resolves to the same source layout every other
    lookup in this suite answers against.
    """
    blob = subprocess.run(
        ["git", "-C", str(REPO), "cat-file", "blob", _PREFIX_AUTOINJECT_BLOB],
        capture_output=True,
        timeout=60,
    )
    if blob.returncode != 0:
        return None
    path = AUTHORITY / "tools" / "autoinject_prefix.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(blob.stdout)
    spec = importlib.util.spec_from_file_location("autoinject_prefix", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class LoaderContractFreshnessTests(AuthorityPatch):
    def test_knowledge_only_home_is_stale_and_names_the_cli_surface(self):
        """Acceptance A + D: the pre-T-1426 shape is never reported current.

        T-1957 makes this stricter than T-1427 left it: `~/.knowledge.md` is
        not a home surface for the CLI either, so a home carrying only that
        file now delivers nothing to EITHER host.
        """
        skill, fixture = _fixture(_tempdir("saipen-loader-knowledge-only-"))
        adapter, surfaces = fixture["adapter"], fixture["surfaces"]
        surfaces[".knowledge.md"].write_text(_block_for(skill), encoding="utf-8")
        self.assertTrue(surfaces[".knowledge.md"].is_file())
        self.assertFalse(surfaces[".AGENTS.md"].exists())

        decision = autoinject.instruction_contract_status(adapter, skill)
        self.assertEqual(decision["status"], "stale", decision)
        self.assertEqual(autoinject.instruction_status(adapter, skill), "stale")
        self.assertIsNotNone(decision["detail"])
        self.assertIn("freebuff CLI", decision["detail"])
        self.assertIn(".AGENTS.md", decision["detail"])

    def test_a_stale_cli_block_reports_stale_naming_its_surface(self):
        """Acceptance B: .AGENTS.md present but stale."""
        skill, fixture = _fixture(_tempdir("saipen-loader-desktop-stale-"))
        adapter, surfaces = fixture["adapter"], fixture["surfaces"]
        surfaces[".knowledge.md"].write_text(_block_for(skill), encoding="utf-8")
        stale = _block_for(skill).replace("SHORTCUT ACTIVATION GATE", "SHORTCUT GATE")
        surfaces[".AGENTS.md"].write_text(stale, encoding="utf-8")

        decision = autoinject.instruction_contract_status(adapter, skill)
        self.assertEqual(decision["status"], "stale", decision)
        self.assertIn("freebuff CLI", decision["detail"])
        self.assertIn(".AGENTS.md", decision["detail"])

    def test_every_home_loader_contract_delivering_current_is_current(self):
        """Acceptance C: every home-scoped loader delivers the current block."""
        skill, fixture = _fixture(_tempdir("saipen-loader-all-current-"))
        adapter, surfaces = fixture["adapter"], fixture["surfaces"]
        block = _block_for(skill)
        surfaces[".knowledge.md"].write_text(block, encoding="utf-8")
        surfaces[".AGENTS.md"].write_text("# user notes\n\n" + block + "\n", encoding="utf-8")

        decision = autoinject.instruction_contract_status(adapter, skill)
        self.assertEqual(decision["status"], "current", decision)
        self.assertEqual(autoinject.instruction_status(adapter, skill), "current")
        self.assertIsNone(decision["detail"])

    def test_a_project_scoped_loader_is_not_applicable_not_a_home_verdict(self):
        """T-1957: a home report must not claim a project reader's delivery.

        The 2026-10-29 desktop build reads `AGENTS.md` under the project root
        and nothing in the home. Reporting it `current` from `~/.AGENTS.md` was
        a false statement about the loader named; reporting it `absent` would
        call a working install broken. Both are avoided by `not-applicable`,
        excluded from the overall status and left to `project_block`.
        """
        skill, fixture = _fixture(_tempdir("saipen-loader-project-scope-"))
        adapter, surfaces = fixture["adapter"], fixture["surfaces"]
        # CLI satisfied; desktop has NO home file at all -- and still must not
        # redden the verdict, because it has no home surface to redden.
        surfaces[".AGENTS.md"].write_text(_block_for(skill), encoding="utf-8")

        decision = autoinject.instruction_contract_status(adapter, skill)
        self.assertEqual(decision["status"], "current", decision)
        desktop = next(
            row for row in decision["deliveries"] if row["loader"] == "FreeBuff Desktop"
        )
        self.assertEqual(desktop["status"], "not-applicable", decision)
        self.assertIsNone(desktop["surface"])

    def test_the_cli_reads_its_first_existing_file_not_the_latest(self):
        """First-existing order: a stale .AGENTS.md shadows .CLAUDE.md."""
        skill, fixture = _fixture(_tempdir("saipen-loader-cli-first-"))
        adapter, surfaces = fixture["adapter"], fixture["surfaces"]
        stale = _block_for(skill).replace("SHORTCUT ACTIVATION GATE", "SHORTCUT GATE")
        surfaces[".AGENTS.md"].write_text(stale, encoding="utf-8")
        surfaces[".CLAUDE.md"].write_text(_block_for(skill), encoding="utf-8")

        decision = autoinject.instruction_contract_status(adapter, skill)
        self.assertEqual(decision["status"], "stale", decision)
        self.assertIn("freebuff CLI", decision["detail"])
        self.assertIn(".AGENTS.md", decision["detail"])

    def test_an_uninstalled_adapter_without_any_surface_is_absent(self):
        skill, fixture = _fixture(_tempdir("saipen-loader-none-"))
        adapter = fixture["adapter"]
        self.assertEqual(autoinject.instruction_status(adapter, skill), "absent")

    def test_an_adapter_without_loader_contracts_keeps_any_surface_semantics(self):
        """No regression for single-surface adapters (opencode/claude/...)."""
        skill, fixture = _fixture(_tempdir("saipen-loader-fallback-"))
        surfaces = fixture["surfaces"]
        surfaces[".knowledge.md"].write_text(_block_for(skill), encoding="utf-8")
        adapter = {
            "id": "codex",
            "instruction_surfaces": [
                str(surfaces[".claude.md"]),
                str(surfaces[".knowledge.md"]),
            ],
        }
        self.assertEqual(autoinject.instruction_status(adapter, skill), "current")

    def test_home_surface_status_carries_the_named_diagnostic(self):
        skill, fixture = _fixture(_tempdir("saipen-loader-diagnostic-"))
        adapter, surfaces = fixture["adapter"], fixture["surfaces"]
        surfaces[".knowledge.md"].write_text(_block_for(skill), encoding="utf-8")
        with unittest.mock.patch.object(
            autoinject,
            "_HOME_ADAPTERS",
            {str(skill.resolve()): adapter},
        ):
            status = autoinject.home_surface_status(skill)
        self.assertEqual(status["surfaces"].get("instruction"), "stale", status)
        self.assertIn("instruction", status["problems"])
        self.assertIn(".AGENTS.md", status["details"]["instruction"])

    @unittest.skipUnless(shutil.which("git"), "git unavailable")
    def test_pre_fix_subject_reported_the_knowledge_only_home_current(self):
        """RED control: the same fixture under the pinned pre-fix subject."""
        module = _load_pre_fix_module()
        if module is None:
            self.skipTest("pinned pre-fix autoinject blob not in this clone")
        skill, fixture = _fixture(_tempdir("saipen-loader-red-control-"))
        adapter, surfaces = fixture["adapter"], fixture["surfaces"]
        surfaces[".knowledge.md"].write_text(_block_for(skill), encoding="utf-8")
        pre_fix = module.instruction_status(adapter, skill)
        self.assertEqual(
            pre_fix,
            "current",
            "the pinned pre-fix subject must exhibit the defect on this fixture",
        )
        self.assertEqual(autoinject.instruction_status(adapter, skill), "stale")


class RegistryDeclarationTests(unittest.TestCase):
    def test_the_registry_declares_the_measured_loader_contracts(self):
        registry = json.loads(
            (REPO / "extensions" / "adapters" / "registry.json").read_text(encoding="utf-8")
        )
        freebuff = next(
            adapter for adapter in registry["adapters"] if adapter.get("id") == "freebuff"
        )
        loaders = freebuff.get("instruction_loaders") or []
        self.assertEqual(
            [loader.get("name") for loader in loaders],
            ["freebuff CLI", "FreeBuff Desktop"],
        )
        self.assertEqual(
            [Path(surface).name for surface in loaders[0]["surfaces"]],
            list(CLI_SURFACES),
        )
        self.assertEqual(loaders[0].get("scope"), "home")
        self.assertEqual(
            loaders[1].get("scope"), "project",
            "FreeBuff Desktop reads the PROJECT root since the 2026-10-29 "
            "update; a home scope would make the verdict claim a delivery it "
            "cannot perform",
        )
        self.assertEqual(loaders[1]["surfaces"], [])
        self.assertEqual(
            list(loaders[1]["project_surfaces"]),
            list(PROJECT_SURFACES),
        )
        self.assertNotIn(
            "~/.knowledge.md",
            loaders[0]["surfaces"],
            "the 0.2.34 CLI reads no *.knowledge.md from the home -- that name "
            "is a PROJECT-file predicate in freebuff.exe",
        )
        self.assertIn("instruction", freebuff.get("freshness_surfaces") or [])

    def test_the_installer_writes_the_surface_each_loader_reads_first(self):
        """The write list must cover the surface a loader actually wins on.

        A loader reads the FIRST existing file of its list, so an installer
        that wrote only the second surface would be shadowed the moment the
        user had a stale first one. `.CLAUDE.md` is a fallback, never a
        requirement, and `~/.knowledge.md` stays written for older CLIs even
        though 0.2.34 no longer reads it -- writing a harmless file is not a
        false claim, reporting delivery from it was (T-1957).
        """
        registry = json.loads(
            (REPO / "extensions" / "adapters" / "registry.json").read_text(encoding="utf-8")
        )
        freebuff = next(
            adapter for adapter in registry["adapters"] if adapter.get("id") == "freebuff"
        )
        written = [Path(s).name for s in freebuff["instruction_surfaces"]]
        self.assertIn(".knowledge.md", written)
        for loader in freebuff["instruction_loaders"]:
            if loader.get("scope", "home") != "home":
                continue
            first = Path(loader["surfaces"][0]).name
            self.assertIn(
                first,
                written,
                f"{loader['name']} reads {first} first, but the installer never "
                f"writes it, so the block it writes is shadowed",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
