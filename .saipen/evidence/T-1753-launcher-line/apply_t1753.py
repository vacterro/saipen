"""Apply the T-1753 change set: exact replacements, counts asserted, endings kept.

Run from the repository root: python -B .saipen/evidence/T-1753-launcher-line/apply_t1753.py
Every replacement is checked before any file is written; a mismatch writes nothing.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path.cwd()
HERE = Path(__file__).resolve().parent

EDITS: list[tuple[str, str, str]] = []


def edit(path: str, old: str, new: str) -> None:
    EDITS.append((path, old, new))


# 1. The template: the launcher line names the runtime root.
edit(
    "saipen/ACTIVATION_BLOCK.md",
    "LAUNCHER: `saipen` not on PATH -> run `{{SAIPEN_HOME}}/bin/saipen` (POSIX,\n"
    "Git Bash) or `{{SAIPEN_HOME}}\\bin\\saipen.cmd` (cmd, PowerShell) with the\n",
    "LAUNCHER: `saipen` not on PATH -> run `{{SAIPEN_ROOT}}/bin/saipen` (POSIX,\n"
    "Git Bash) or `{{SAIPEN_ROOT}}\\bin\\saipen.cmd` (cmd, PowerShell) with the\n",
)

# 2. The Python renderer and the freshness check.
edit(
    "tools/autoinject.py",
    'def rendered_activation_block(skill_install_dir: Path) -> str:\n'
    '    """The canonical block as the injector would install it for this home."""\n'
    '    template = activation_template_path().read_text(encoding="utf-8")\n'
    '    return template.replace("{{SAIPEN_HOME}}", str(skill_install_dir))\n',
    "#: The two variables of the activation template. `{{SAIPEN_HOME}}` is the\n"
    "#: PROTOCOL directory the block sends an agent to for BOOT.md and STYLE.md;\n"
    "#: `{{SAIPEN_ROOT}}` is the runtime root whose `bin/` holds the launcher -- the\n"
    "#: same directory in a flattened install, its parent in a source clone. One\n"
    "#: variable for both printed `<clone>/saipen/bin/saipen`, a path that does not\n"
    "#: exist (T-1753). The root is never chosen on its own: every renderer derives\n"
    "#: it from the home it substitutes.\n"
    'HOME_VARIABLE = "{{SAIPEN_HOME}}"\n'
    'ROOT_VARIABLE = "{{SAIPEN_ROOT}}"\n'
    '_TEMPLATE_VARIABLE = re.compile(r"\\{\\{SAIPEN_(?:HOME|ROOT)\\}\\}")\n'
    "\n"
    "\n"
    'def rendered_activation_block(skill_install_dir: Path) -> str:\n'
    '    """The canonical block as the injector would install it for this home."""\n'
    '    template = activation_template_path().read_text(encoding="utf-8")\n'
    "    root = protocol_home_runtime_root(Path(skill_install_dir))\n"
    "    return template.replace(HOME_VARIABLE, str(skill_install_dir)).replace(\n"
    "        ROOT_VARIABLE, str(root)\n"
    "    )\n",
)
edit(
    "tools/autoinject.py",
    'def _activation_home(template_block: str, installed_block: str) -> str | None:\n'
    '    """The SAIPEN home an installed block names, or None if it is not this\n'
    "    template.\n"
    "\n"
    "    `{{SAIPEN_HOME}}` is a VARIABLE. Matching the rendered block byte-for-byte\n"
    "    treats one particular substitution as part of the contract, which is how a\n"
    "    healthy install reported stale forever (T-1337): a block pointing at the\n"
    "    source clone differs from a block pointing at the installed skill copy in\n"
    "    the home and nowhere else, and no amount of re-injection can make the two\n"
    "    spellings equal. Split on the placeholder, require every literal segment to\n"
    "    match in order, and require every gap to carry the SAME home.\n"
    '    """\n'
    '    segments = template_block.split("{{SAIPEN_HOME}}")\n'
    "    if len(segments) == 1:\n"
    '        return "" if installed_block == template_block else None\n'
    "    home: str | None = None\n"
    "    rest = installed_block\n"
    "    for index, segment in enumerate(segments):\n"
    "        if index == 0:\n"
    "            if not rest.startswith(segment):\n"
    "                return None\n"
    "            rest = rest[len(segment) :]\n"
    "            continue\n"
    "        if index == len(segments) - 1:\n"
    "            if not rest.endswith(segment):\n"
    "                return None\n"
    "            candidate = rest[: len(rest) - len(segment)]\n"
    "        else:\n"
    "            position = rest.find(segment)\n"
    "            if position < 0:\n"
    "                return None\n"
    "            candidate = rest[:position]\n"
    "            rest = rest[position + len(segment) :]\n"
    "        if home is None:\n"
    "            home = candidate\n"
    "        elif home != candidate:\n"
    "            return None\n"
    "    return home\n",
    "def _activation_values(template_block: str, installed_block: str) -> dict[str, str] | None:\n"
    '    """What each template variable says in an installed block, or None if the\n'
    "    block is not this template.\n"
    "\n"
    "    `{{SAIPEN_HOME}}` and `{{SAIPEN_ROOT}}` are VARIABLES. Matching the rendered\n"
    "    block byte-for-byte treats one particular substitution as part of the\n"
    "    contract, which is how a healthy install reported stale forever (T-1337): a\n"
    "    block pointing at the source clone differs from a block pointing at the\n"
    "    installed skill copy in its paths and nowhere else, and no amount of\n"
    "    re-injection can make the two spellings equal. Split on the variables,\n"
    "    require every literal segment to match in order, and require every gap of\n"
    "    one variable to carry the SAME value.\n"
    '    """\n'
    "    segments = _TEMPLATE_VARIABLE.split(template_block)\n"
    "    names = _TEMPLATE_VARIABLE.findall(template_block)\n"
    "    if not names:\n"
    "        return {} if installed_block == template_block else None\n"
    "    if not installed_block.startswith(segments[0]):\n"
    "        return None\n"
    "    rest = installed_block[len(segments[0]) :]\n"
    "    values: dict[str, str] = {}\n"
    "    for index, name in enumerate(names, start=1):\n"
    "        segment = segments[index]\n"
    "        if index == len(names):\n"
    "            if not rest.endswith(segment):\n"
    "                return None\n"
    "            candidate = rest[: len(rest) - len(segment)]\n"
    "        else:\n"
    "            position = rest.find(segment)\n"
    "            if position < 0:\n"
    "                return None\n"
    "            candidate = rest[:position]\n"
    "            rest = rest[position + len(segment) :]\n"
    "        if values.setdefault(name, candidate) != candidate:\n"
    "            return None\n"
    "    return values\n"
    "\n"
    "\n"
    "def _activation_home(template_block: str, installed_block: str) -> str | None:\n"
    '    """The SAIPEN home an installed block names, or None if it is not this\n'
    '    template (`_activation_values`)."""\n'
    "    values = _activation_values(template_block, installed_block)\n"
    "    if values is None:\n"
    "        return None\n"
    '    return values.get(HOME_VARIABLE, "")\n',
)
edit(
    "tools/autoinject.py",
    "        return same_runtime_generation(HOME, protocol_home_runtime_root(Path(home.strip())))\n"
    "    except OSError:\n"
    "        return False\n"
    "\n"
    "\n"
    "def _installed_block_status(\n",
    "        return same_runtime_generation(HOME, protocol_home_runtime_root(Path(home.strip())))\n"
    "    except OSError:\n"
    "        return False\n"
    "\n"
    "\n"
    "def _names_its_runtime_root(home: str, root: str | None) -> bool:\n"
    '    """Does the launcher line name the runtime root of the block\'s own home?\n'
    "\n"
    "    T-1753: the launcher is `<root>/bin/saipen`, and a block whose launcher\n"
    "    line names another directory sends a cold agent to a dead or foreign path\n"
    "    while every document pointer still resolves. The old injector wrote the\n"
    "    protocol directory there, so its blocks fail this and the next repair\n"
    "    replaces them. A template without the variable has nothing to prove.\n"
    '    """\n'
    "    if root is None:\n"
    "        return True\n"
    "    try:\n"
    "        return os.path.samefile(\n"
    "            root.strip(), protocol_home_runtime_root(Path(home.strip()))\n"
    "        )\n"
    "    except (OSError, ValueError):\n"
    "        return False\n"
    "\n"
    "\n"
    "def _installed_block_status(\n",
)
edit(
    "tools/autoinject.py",
    "    if template_block is not None:\n"
    '        named = _activation_home(template_block.replace("\\r\\n", "\\n").strip(), installed)\n'
    "        if named is not None and _names_a_real_home(named):\n"
    '            return "current"\n'
    '    return "stale"\n',
    "    if template_block is not None:\n"
    '        values = _activation_values(template_block.replace("\\r\\n", "\\n").strip(), installed)\n'
    "        if values is not None:\n"
    '            named = values.get(HOME_VARIABLE, "")\n'
    "            if _names_a_real_home(named) and _names_its_runtime_root(\n"
    "                named, values.get(ROOT_VARIABLE)\n"
    "            ):\n"
    '                return "current"\n'
    '    return "stale"\n',
)

# 3. The Windows injector (CRLF file; written as LF here, converted below).
edit(
    "bootstrap/inject.ps1",
    "# ONE activation template (SRC-028:R009 / SRC-030 Part 8): the semantic block\n"
    "# is rendered from saipen/ACTIVATION_BLOCK.md; only the SAIPEN home path is\n"
    "# substituted. This script no longer carries its own copy of the block.\n",
    "# ONE activation template (SRC-028:R009 / SRC-030 Part 8): the semantic block\n"
    "# is rendered from saipen/ACTIVATION_BLOCK.md; only the SAIPEN home path and\n"
    "# its runtime root, the folder holding bin/ (T-1753), are substituted. This\n"
    "# script no longer carries its own copy of the block.\n",
)
edit(
    "bootstrap/inject.ps1",
    "$blockCore = $blockCore.Replace('{{SAIPEN_HOME}}', $SkillHome)\n",
    "$blockCore = $blockCore.Replace('{{SAIPEN_HOME}}', $SkillHome)\n"
    "$blockCore = $blockCore.Replace('{{SAIPEN_ROOT}}', $Root)\n",
)

# 4. The POSIX injector.
edit(
    "bootstrap/inject.sh",
    "# ONE activation template (SRC-028:R009 / SRC-030 Part 8): rendered from\n"
    "# saipen/ACTIVATION_BLOCK.md with only the SAIPEN home substituted. Bash\n"
    "# parameter expansion, not sed, so a home path containing backslashes or\n"
    "# ampersands cannot corrupt the render.\n"
    'TEMPLATE_TEXT="$(cat "$TEMPLATE")"\n'
    'BLOCK="${TEMPLATE_TEXT//\\{\\{SAIPEN_HOME\\}\\}/$SKILL_HOME}"\n',
    "# ONE activation template (SRC-028:R009 / SRC-030 Part 8): rendered from\n"
    "# saipen/ACTIVATION_BLOCK.md with only the SAIPEN home and its runtime root,\n"
    "# the folder holding bin/ (T-1753), substituted. Bash parameter expansion,\n"
    "# not sed, so a home path containing backslashes or ampersands cannot corrupt\n"
    "# the render.\n"
    'TEMPLATE_TEXT="$(cat "$TEMPLATE")"\n'
    'BLOCK="${TEMPLATE_TEXT//\\{\\{SAIPEN_HOME\\}\\}/$SKILL_HOME}"\n'
    'BLOCK="${BLOCK//\\{\\{SAIPEN_ROOT\\}\\}/$ROOT}"\n',
)

# 5. The validator names both variables of the template.
edit(
    "tools/validate.py",
    '        "<!-- SAIPEN:END -->",\n'
    '        "{{SAIPEN_HOME}}",\n'
    "    ):\n",
    '        "<!-- SAIPEN:END -->",\n'
    '        "{{SAIPEN_HOME}}",\n'
    '        "{{SAIPEN_ROOT}}",\n'
    "    ):\n",
)

# 6. Its red control.
edit(
    "tools/audit_checks.py",
    'def drop_home_placeholder(text: str) -> str:\n'
    '    """Strip the substitution marker the injector rewrites per home."""\n'
    '    return text.replace("{{SAIPEN_HOME}}", "SAIPEN_HOME")\n',
    'def drop_home_placeholder(text: str) -> str:\n'
    '    """Strip the substitution marker the injector rewrites per home."""\n'
    '    return text.replace("{{SAIPEN_HOME}}", "SAIPEN_HOME")\n'
    "\n"
    "\n"
    "def launcher_under_protocol_dir(text: str) -> str:\n"
    '    """Point the launcher line back at the protocol directory (T-1753)."""\n'
    '    return text.replace("{{SAIPEN_ROOT}}", "{{SAIPEN_HOME}}")\n',
)
edit(
    "tools/audit_checks.py",
    '            drop_home_placeholder,\n'
    "            \"ACTIVATION_BLOCK.md missing '{{SAIPEN_HOME}}'\",\n"
    "        ),\n",
    '            drop_home_placeholder,\n'
    "            \"ACTIVATION_BLOCK.md missing '{{SAIPEN_HOME}}'\",\n"
    "        ),\n"
    "        (\n"
    '            "activation template launcher line loses its root placeholder",\n'
    "            ACTIVATION,\n"
    "            launcher_under_protocol_dir,\n"
    "            \"ACTIVATION_BLOCK.md missing '{{SAIPEN_ROOT}}'\",\n"
    "        ),\n",
)

# 7. Neighbour pins that named the defect or rendered one variable only.
edit(
    "tools/test_t1645_zero_hunt.py",
    '        self.assertIn("LAUNCHER: `saipen` not on PATH -> run `{{SAIPEN_HOME}}/bin/saipen`", block)\n'
    '        self.assertIn("`{{SAIPEN_HOME}}\\\\bin\\\\saipen.cmd`", block)\n',
    "        # T-1753: the launcher sits in the runtime root, not the protocol directory.\n"
    '        self.assertIn("LAUNCHER: `saipen` not on PATH -> run `{{SAIPEN_ROOT}}/bin/saipen`", block)\n'
    '        self.assertIn("`{{SAIPEN_ROOT}}\\\\bin\\\\saipen.cmd`", block)\n',
)
edit(
    "tools/test_adapter_parity.py",
    "        template = TEMPLATE.read_text(encoding=\"utf-8\")\n"
    "        skill_home = (REPO / \"saipen\").resolve()\n"
    "        expected = (\n"
    "            template.replace(\"{{SAIPEN_HOME}}\", str(skill_home)).replace(\"\\r\\n\", \"\\n\").strip()\n"
    "        )\n",
    "        skill_home = (REPO / \"saipen\").resolve()\n"
    "        # T-1753: both template variables, rendered by the one Python owner.\n"
    "        expected = (\n"
    "            autoinject.rendered_activation_block(skill_home).replace(\"\\r\\n\", \"\\n\").strip()\n"
    "        )\n",
)
edit(
    "tools/test_instruction_home_parity.py",
    "        rendered = _template_block().replace(\"{{SAIPEN_HOME}}\", block_home)\n",
    "        # T-1753: the launcher variable is derived from the home, as the\n"
    "        # renderers derive it.\n"
    "        root = autoinject.protocol_home_runtime_root(Path(block_home))\n"
    "        rendered = _template_block().replace(\"{{SAIPEN_HOME}}\", block_home)\n"
    "        rendered = rendered.replace(\"{{SAIPEN_ROOT}}\", str(root))\n",
)
edit(
    "tools/test_host_bootstrap.py",
    "            self.assertNotIn(\"{{SAIPEN_HOME}}\", text)\n",
    "            self.assertNotIn(\"{{SAIPEN_HOME}}\", text)\n"
    "            self.assertNotIn(\"{{SAIPEN_ROOT}}\", text)\n",
)


def main() -> int:
    planned: dict[str, bytes] = {}
    for rel, old, new in EDITS:
        path = ROOT / rel
        data = planned.get(rel) or path.read_bytes()
        crlf = b"\r\n" in data
        old_b = old.encode("utf-8")
        new_b = new.encode("utf-8")
        if crlf:
            old_b = old_b.replace(b"\n", b"\r\n")
            new_b = new_b.replace(b"\n", b"\r\n")
        count = data.count(old_b)
        if count != 1:
            print(f"ABORT: {rel}: expected exactly one match, found {count}:\n{old[:160]}")
            return 1
        planned[rel] = data.replace(old_b, new_b, 1)
    if "--check" in sys.argv:
        print(f"CHECK OK: {len(EDITS)} edits in {len(planned)} files match exactly once")
        return 0
    for rel, data in planned.items():
        (ROOT / rel).write_bytes(data)
        print(f"patched {rel}")
    target = ROOT / "tools" / "test_t1753_launcher_line.py"
    shutil.copyfile(HERE / "draft" / "test_t1753_launcher_line.py", target)
    print(f"wrote {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
