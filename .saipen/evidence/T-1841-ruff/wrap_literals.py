"""Bounded local formatting aid; accept only an identical Python AST."""
import ast
import io
import json
import re
import tokenize
import warnings
from pathlib import Path

root = Path.cwd().resolve()
base = root / ".saipen/evidence/T-1841-ruff"
findings = json.loads((base / "after-format.json").read_text())
allowed = set(json.loads((base / "prefix-manifest.json").read_text())["files"])


def tree(text, *, expression=False):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return ast.dump(ast.parse(text, mode="eval" if expression else "exec"),
                        include_attributes=False)


def chunks(literal, limit):
    match = re.match(r"(?i)^([rubf]*)(\"\"\"|'''|\"|')", literal)
    if match is None:
        return None
    prefix, quote = match.groups()
    body = literal[match.end():-len(quote)]
    result = []
    while len(body) > limit:
        candidates = list(range(min(limit, len(body) - 1), 0, -1))
        candidates.sort(key=lambda cut: (not body[cut - 1].isspace(), -cut))
        current = prefix + quote + body + quote
        for cut in candidates:
            left = prefix + quote + body[:cut] + quote
            right = prefix + quote + body[cut:] + quote
            try:
                equivalent = tree("(" + left + " " + right + ")", expression=True) == tree(
                    current, expression=True
                )
            except (SyntaxError, ValueError):
                continue
            if equivalent:
                result.append(left)
                body = body[cut:]
                break
        else:
            return None
    result.append(prefix + quote + body + quote)
    return result


handled = []
skipped = []
for item in sorted(findings, key=lambda item: (item["filename"], -item["location"]["row"])):
    if item["code"] != "E501":
        continue
    path = Path(item["filename"]).resolve()
    relative = path.relative_to(root).as_posix()
    if relative not in allowed:
        raise RuntimeError("Unexpected source scope")
    raw = path.read_bytes().decode("utf-8")
    lines = raw.splitlines(keepends=True)
    row = item["location"]["row"]
    depth = 0
    literals = []
    for token in tokenize.generate_tokens(io.StringIO(raw).readline):
        if token.type == tokenize.STRING and token.start[0] == token.end[0] == row:
            literals.append((len(token.string), token, depth))
        if token.type == tokenize.OP:
            if token.string in ("(", "[", "{"):
                depth += 1
            elif token.string in (")", "]", "}"):
                depth -= 1
    if not literals:
        skipped.append([relative, row])
        continue
    _, token, depth = max(literals, key=lambda item: item[0])
    line = lines[row - 1]
    leading = len(line) - len(line.lstrip())
    column = token.start[1] if depth else leading + 4
    pieces = chunks(token.string, max(16, 92 - column - 8))
    if not pieces or len(pieces) < 2:
        skipped.append([relative, row])
        continue
    if depth:
        replacement = ("\n" + " " * column).join(pieces)
    else:
        replacement = "(\n" + "\n".join(" " * column + piece for piece in pieces)
        replacement += "\n" + " " * leading + ")"
    lines[row - 1] = line[:token.start[1]] + replacement + line[token.end[1]:]
    changed = "".join(lines)
    try:
        equivalent = tree(raw) == tree(changed)
    except (SyntaxError, ValueError):
        equivalent = False
    if not equivalent:
        skipped.append([relative, row])
        continue
    path.write_text(changed, encoding="utf-8", newline="")
    handled.append([relative, row])
report = {"handled": handled, "manual": skipped, "guard": "identical full-file AST per edit"}
(base / "literal-wrap-report.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({"handled": len(handled), "manual": skipped}))
