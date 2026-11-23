"""Text-mode production subprocesses must decode the declared UTF-8 contract."""

from __future__ import annotations

import ast
import copy
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
FUNCTIONS = {"run", "Popen", "check_output", "check_call", "call"}


def production_files():
    for directory in ("tools", "extensions", "bootstrap"):
        for path in sorted((ROOT / directory).rglob("*.py")):
            if path.name.startswith("test_") or "tests" in path.relative_to(ROOT).parts:
                continue
            yield path


def sites(text: str):
    tree = ast.parse(text)
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}

    def scope(node):
        while node in parents:
            node = parents[node]
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                return node
        return tree

    dictionaries = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign):
            target, value = node.target, node.value
        else:
            continue
        if (
            isinstance(target, ast.Name)
            and isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id == "dict"
        ):
            dictionaries.setdefault((scope(node), target.id), []).append((node.lineno, value))
    modules = {"subprocess"}
    imported = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(
                alias.asname or alias.name for alias in node.names if alias.name == "subprocess"
            )
        elif isinstance(node, ast.ImportFrom) and node.module == "subprocess":
            imported.update({alias.asname or alias.name: alias.name for alias in node.names})
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = None
        if (
            isinstance(fn, ast.Attribute)
            and isinstance(fn.value, ast.Name)
            and fn.value.id in modules
        ):
            name = fn.attr
        elif isinstance(fn, ast.Name):
            name = imported.get(fn.id)
        if name not in FUNCTIONS:
            continue
        kw = {}
        for item in node.keywords:
            if item.arg is not None:
                kw[item.arg] = item
                continue
            if not isinstance(item.value, ast.Name):
                raise ValueError(f"unreviewed subprocess kwargs at line {node.lineno}")
            candidates = [
                entry
                for entry in dictionaries.get((scope(node), item.value.id), [])
                if entry[0] < node.lineno
            ]
            if not candidates:
                raise ValueError(f"unreviewed subprocess kwargs at line {node.lineno}")
            dictionary = max(candidates, key=lambda entry: entry[0])[1]
            for setting in dictionary.keywords:
                if setting.arg is None:
                    raise ValueError(f"unreviewed subprocess kwargs at line {node.lineno}")
                kw[setting.arg] = setting
        if any(
            key in kw and not isinstance(kw[key].value, ast.Constant)
            for key in ("text", "universal_newlines")
        ):
            raise ValueError(f"unreviewed dynamic text flag at line {node.lineno}")
        text_kw = next(
            (
                kw[key]
                for key in ("text", "universal_newlines")
                if key in kw
                and isinstance(kw[key].value, ast.Constant)
                and kw[key].value.value is True
            ),
            None,
        )
        if text_kw is not None:
            yield node, name, kw, text_kw


def decoding_probe(node, name, settings=None):
    """Execute the site's actual decoding keywords with a real UTF-8 child."""
    settings = node.keywords if settings is None else settings.values()
    keywords = [
        copy.deepcopy(kw)
        for kw in settings
        if kw.arg in {"text", "universal_newlines", "encoding", "errors"}
    ]
    child = [
        sys.executable,
        "-c",
        "import sys; sys.stdout.buffer.write(bytes.fromhex('c3b5c3a4c3b6c3bc'))",
    ]
    call = ast.Call(
        func=ast.Attribute(
            value=ast.Name(id="subprocess", ctx=ast.Load()), attr=name, ctx=ast.Load()
        ),
        args=[ast.List(elts=[ast.Constant(value=item) for item in child], ctx=ast.Load())],
        keywords=keywords,
    )
    if name == "Popen":
        call.keywords.append(
            ast.keyword(
                arg="stdout",
                value=ast.Attribute(
                    value=ast.Name(id="subprocess", ctx=ast.Load()), attr="PIPE", ctx=ast.Load()
                ),
            )
        )
    elif name == "run":
        call.keywords.append(ast.keyword(arg="capture_output", value=ast.Constant(value=True)))
    elif name != "check_output":
        raise ValueError(f"text-mode {name} has no captured output; requires individual review")
    expression = ast.fix_missing_locations(ast.Expression(body=call))
    with patch.object(subprocess, "_text_encoding", return_value="cp1251"):
        result = eval(
            compile(expression, "<decoding-keywords>", "eval"), {"subprocess": subprocess}
        )
        if name == "Popen":
            output, _ = result.communicate(timeout=10)
        elif name == "run":
            output = result.stdout
        else:
            output = result
    return output == "õäöü"


class SubprocessUtf8Contract(unittest.TestCase):
    def test_no_production_text_call_uses_the_implicit_locale(self):
        missing = []
        for path in production_files():
            for node, name, keywords, _text_kw in sites(path.read_text(encoding="utf-8")):
                if "encoding" not in keywords:
                    missing.append(f"{path.relative_to(ROOT)}:{node.lineno}: {name}")
        self.assertEqual(missing, [], "explicit child-output encoding is required")

    def test_utf8_sites_preserve_a_real_child_output_under_cp1251(self):
        checked = 0
        for path in production_files():
            for node, name, keywords, _text_kw in sites(path.read_text(encoding="utf-8")):
                encoding = keywords.get("encoding")
                if encoding is None or not isinstance(encoding.value, ast.Constant):
                    continue
                if encoding.value.value != "utf-8":
                    continue
                with self.subTest(path=str(path.relative_to(ROOT)), line=node.lineno):
                    self.assertTrue(decoding_probe(node, name, keywords))
                checked += 1
        self.assertGreater(checked, 0, "the decoding oracle tested no production site")

    def test_missing_encoding_red_control_really_corrupts_utf8(self):
        call = ast.parse("subprocess.run(['unused'], text=True)", mode="eval").body
        self.assertFalse(decoding_probe(call, "run"))

    def test_dict_built_text_settings_are_part_of_the_inventory(self):
        source = "def child():\n    options = dict(text=True)\n    subprocess.run([], **options)\n"
        before = list(sites(source))
        after = list(sites(source.replace("text=True", 'text=True, encoding="utf-8"')))
        self.assertEqual(len(before), 1)
        self.assertNotIn("encoding", before[0][2])
        self.assertIn("encoding", after[0][2])
        self.assertFalse(decoding_probe(before[0][0], before[0][1], before[0][2]))
        self.assertTrue(decoding_probe(after[0][0], after[0][1], after[0][2]))

    def test_unknown_forwarded_settings_are_not_silently_excluded(self):
        source = "def child(options):\n    subprocess.run([], **options)\n"
        with self.assertRaisesRegex(ValueError, "unreviewed subprocess kwargs"):
            list(sites(source))

    def test_import_aliases_are_in_the_same_inventory(self):
        source = (
            "import subprocess as child\n"
            "from subprocess import Popen as spawn\n"
            "child.run([], text=True)\n"
            "spawn([], universal_newlines=True)\n"
        )
        self.assertEqual({name for _node, name, _kw, _text in sites(source)}, {"run", "Popen"})


if __name__ == "__main__":
    unittest.main()
