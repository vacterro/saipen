"""Read-only review aid: inventory option spellings absent from the draft table."""

import ast
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
tree = ast.parse(text)
table = next(node for node in tree.body if isinstance(node, ast.Assign)
             and any(isinstance(target, ast.Name) and target.id == "_VALUE_OPTIONS"
                     for target in node.targets))
known = ast.literal_eval(table.value.args[0])
flags = {}
for node in ast.walk(tree):
    if (isinstance(node, ast.Constant) and isinstance(node.value, str)
            and re.fullmatch(r"--[a-zA-Z0-9_-]+", node.value)):
        flags.setdefault(node.value, set()).add(node.lineno)
for flag in sorted(set(flags) - known):
    print(flag, ",".join(map(str, sorted(flags[flag]))))
