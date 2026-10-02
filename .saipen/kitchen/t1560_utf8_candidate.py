"""Inventory and prepare the queued UTF-8 sweep without editing the tested tree."""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
DRAFT = ROOT / ".saipen/evidence/T-1560-utf8-candidate"
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
        if (isinstance(target, ast.Name) and isinstance(value, ast.Call)
                and isinstance(value.func, ast.Name) and value.func.id == "dict"):
            dictionaries.setdefault((scope(node), target.id), []).append((node.lineno, value))
    modules = {"subprocess"}
    imported = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.asname or alias.name for alias in node.names if alias.name == "subprocess")
        elif isinstance(node, ast.ImportFrom) and node.module == "subprocess":
            imported.update({alias.asname or alias.name: alias.name for alias in node.names})
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = None
        if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and fn.value.id in modules:
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
            candidates = [entry for entry in dictionaries.get((scope(node), item.value.id), [])
                          if entry[0] < node.lineno]
            if not candidates:
                raise ValueError(f"unreviewed subprocess kwargs at line {node.lineno}")
            dictionary = max(candidates, key=lambda entry: entry[0])[1]
            for setting in dictionary.keywords:
                if setting.arg is None:
                    raise ValueError(f"unreviewed subprocess kwargs at line {node.lineno}")
                kw[setting.arg] = setting
        if any(key in kw and not isinstance(kw[key].value, ast.Constant)
               for key in ("text", "universal_newlines")):
            raise ValueError(f"unreviewed dynamic text flag at line {node.lineno}")
        text_kw = next((kw[key] for key in ("text", "universal_newlines")
                        if key in kw and isinstance(kw[key].value, ast.Constant)
                        and kw[key].value.value is True), None)
        if text_kw is not None:
            yield node, name, kw, text_kw


def inventory():
    missing = []
    explicit = 0
    for path in production_files():
        for node, name, kw, text_kw in sites(path.read_text(encoding="utf-8")):
            if "encoding" in kw:
                explicit += 1
                continue
            missing.append({"path": path.relative_to(ROOT).as_posix(), "line": node.lineno, "callee": name})
    return missing, explicit


def build_draft():
    missing, explicit = inventory()
    by_path = {}
    for row in missing:
        by_path.setdefault(row["path"], []).append(row)
    manifest = {"ticket": "T-1560", "scope": ["tools", "extensions", "bootstrap"],
                "missing_before": len(missing), "explicit_before": explicit,
                "limitations": ["constant text flags, including local dict-built kwargs; unresolved dynamic settings refuse"],
                "files": []}
    for relative in by_path:
        path = ROOT / relative
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        lines = text.splitlines(keepends=True)
        offsets = []
        cursor = 0
        for line in lines:
            offsets.append(cursor)
            cursor += len(line.encode("utf-8"))
        points = []
        for node, name, kw, text_kw in sites(text):
            if "encoding" not in kw:
                value = text_kw.value
                line = lines[value.end_lineno - 1]
                addition = b', encoding="utf-8"'
                if len(line.rstrip("\r\n")) + len(addition) > 100:
                    leading = line[:len(line) - len(line.lstrip())]
                    indent = leading if text_kw.col_offset == len(leading) else leading + "    "
                    newline = "\r\n" if line.endswith("\r\n") else "\n"
                    addition = ("," + newline + indent + 'encoding="utf-8"').encode("utf-8")
                    prefix = line.encode("utf-8")[:value.end_col_offset].decode("utf-8")
                    if len(prefix) + 1 > 100:
                        keyword_at = offsets[text_kw.lineno - 1] + text_kw.col_offset
                        trimmed_at = keyword_at
                        while raw[trimmed_at - 1:trimmed_at] in (b" ", b"\t"):
                            trimmed_at -= 1
                        points.append((trimmed_at, keyword_at, (newline + indent).encode("utf-8")))
                point = offsets[value.end_lineno - 1] + value.end_col_offset
                points.append((point, point, addition))
        updated = raw
        for start, end, addition in sorted(points, reverse=True):
            updated = updated[:start] + addition + updated[end:]
        ast.parse(updated.decode("utf-8"))
        target = DRAFT / (relative + ".draft")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(updated)
        manifest["files"].append({"path": relative, "before_sha256": hashlib.sha256(raw).hexdigest(),
                                  "after_sha256": hashlib.sha256(updated).hexdigest(), "sites": by_path[relative]})
    DRAFT.mkdir(parents=True, exist_ok=True)
    (DRAFT / "ruff.toml").write_bytes((ROOT / "ruff.toml").read_bytes())
    (DRAFT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def decoding_probe(node, name, settings=None):
    """Execute the site's actual decoding keywords with a real UTF-8 child."""
    settings = node.keywords if settings is None else settings.values()
    keywords = [copy.deepcopy(kw) for kw in settings
                if kw.arg in {"text", "universal_newlines", "encoding", "errors"}]
    child = [sys.executable, "-c", "import sys; sys.stdout.buffer.write(bytes.fromhex('c3b5c3a4c3b6c3bc'))"]
    call = ast.Call(func=ast.Attribute(value=ast.Name(id="subprocess", ctx=ast.Load()), attr=name, ctx=ast.Load()),
                    args=[ast.List(elts=[ast.Constant(value=item) for item in child], ctx=ast.Load())], keywords=keywords)
    if name == "Popen":
        call.keywords.append(ast.keyword(arg="stdout", value=ast.Attribute(value=ast.Name(id="subprocess", ctx=ast.Load()), attr="PIPE", ctx=ast.Load())))
    elif name == "run":
        call.keywords.append(ast.keyword(arg="capture_output", value=ast.Constant(value=True)))
    elif name != "check_output":
        raise ValueError(f"text-mode {name} has no captured output; requires individual review")
    expression = ast.fix_missing_locations(ast.Expression(body=call))
    with patch.object(subprocess, "_text_encoding", return_value="cp1251"):
        result = eval(compile(expression, "<decoding-keywords>", "eval"), {"subprocess": subprocess})
        if name == "Popen":
            output, _ = result.communicate(timeout=10)
        elif name == "run":
            output = result.stdout
        else:
            output = result
    return output == "õäöü"


def check_draft():
    manifest = json.loads((DRAFT / "manifest.json").read_text(encoding="utf-8"))
    results = []
    for record in manifest["files"]:
        relative = record["path"]
        raw = (ROOT / relative).read_bytes()
        original = raw.decode("utf-8")
        if hashlib.sha256(raw).hexdigest() != record["before_sha256"]:
            raise RuntimeError(f"draft source changed: {relative}")
        before = list(sites(original))
        after = list(sites((DRAFT / (relative + ".draft")).read_text(encoding="utf-8")))
        for old, new in zip(before, after, strict=True):
            if "encoding" in old[2]:
                continue
            red = decoding_probe(old[0], old[1], old[2])
            green = decoding_probe(new[0], new[1], new[2])
            results.append({"path": relative, "line": old[0].lineno, "callee": old[1],
                            "old_preserves_utf8": red, "candidate_preserves_utf8": green})
    (DRAFT / "decoding-controls.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    bad = [row for row in results if row["old_preserves_utf8"] or not row["candidate_preserves_utf8"]]
    print(json.dumps({"controls": len(results), "failures": bad}, ensure_ascii=False))
    return bool(bad)


if "--draft" in sys.argv:
    manifest = build_draft()
    print(json.dumps({"missing": manifest["missing_before"], "files": len(manifest["files"])}))
elif "--check-draft" in sys.argv:
    sys.exit(check_draft())
else:
    missing, explicit = inventory()
    print(json.dumps({"missing": len(missing), "explicit": explicit, "sites": missing}, ensure_ascii=False, indent=2))
