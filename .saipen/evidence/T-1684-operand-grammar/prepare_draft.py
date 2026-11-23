import ast
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

evidence = Path(__file__).resolve().parent
root = evidence.parents[2]
scratch = Path(tempfile.mkdtemp(prefix='saipen-t1684-draft-'))
draft = scratch / 'project'
sys.path.insert(0, str(root / 'tools'))
from saipen_engine.test_runner import _ignore_copy


def ignore(directory, names):
    extra = {'.saipen'} if Path(directory) == root else set()
    return _ignore_copy(directory, names) | {name for name in names if name in extra}


shutil.copytree(root, draft, symlinks=True, ignore=ignore)
(evidence / 'scratch.json').write_text(json.dumps({'scratch': str(scratch), 'project': str(draft)},
                                                indent=2) + '\n', encoding='utf-8')
paths = ['tools/saipen.py', 'tools/saipen_engine/commands.py',
         'tools/saipen_engine/command_effects.py', 'tools/saipen_engine/cli_grammar.py',
         'tools/test_t1684_operand_grammar.py']
baseline = {}
for relative in paths:
    path = root / relative
    if path.is_file():
        saved = evidence / 'pre' / relative
        saved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, saved)
        baseline[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    else:
        baseline[relative] = None
(evidence / 'paths.json').write_text(json.dumps(paths, indent=2) + '\n', encoding='utf-8')
(evidence / 'baseline.json').write_text(json.dumps(baseline, indent=2) + '\n', encoding='utf-8')
cli_path = draft / 'tools/saipen.py'
text = cli_path.read_text(encoding='utf-8-sig')
module = ast.parse(text)
assignment = next(node for node in module.body if isinstance(node, ast.Assign)
                  and any(isinstance(target, ast.Name) and target.id == '_VALUE_OPTIONS'
                          for target in node.targets))
function = next(node for node in module.body if isinstance(node, ast.FunctionDef)
                and node.name == '_option_value_positions')
options = ast.get_source_segment(text, assignment).replace('_VALUE_OPTIONS', 'VALUE_OPTIONS', 1)
positions = ast.get_source_segment(text, function).replace('_option_value_positions',
                                                          'option_value_positions', 1)
positions = positions.replace('_VALUE_OPTIONS', 'VALUE_OPTIONS').replace('argv: list[str]',
                                                                       'argv: Sequence[str]')
grammar = ('"""Shared lexical roles for shell-decoded SAIPEN option operands."""\n\n'
           'from __future__ import annotations\n\n'
           'from collections.abc import Collection, Sequence\n\n\n' + options + '\n\n\n'
           + positions + '\n\n\n'
           'def has_option(argv: Sequence[str], options: Collection[str]) -> bool:\n'
           '    """Only an unconsumed token before the real boundary is a switch."""\n'
           '    values = option_value_positions(argv)\n'
           '    for index, token in enumerate(argv):\n'
           '        if index in values:\n'
           '            continue\n'
           '        if token == "--":\n'
           '            break\n'
           '        if token in options:\n'
           '            return True\n'
           '    return False\n')
(draft / 'tools/saipen_engine/cli_grammar.py').write_text(grammar, encoding='utf-8')
lines = text.splitlines(keepends=True)
imports = ('from saipen_engine.cli_grammar import has_option as _has_cli_option  # noqa: E402\n'
           'from saipen_engine.cli_grammar import (  # noqa: E402\n'
           '    option_value_positions as _option_value_positions,\n'
           ')\n')
text = ''.join(lines[:assignment.lineno-1]) + imports + ''.join(lines[function.end_lineno:])
text = text.replace('    raw_args = list(argv if argv is not None else sys.argv[1:])\n',
                    '    raw_args = list(argv if argv is not None else sys.argv[1:])\n'
                    '    value_positions = _option_value_positions(raw_args)\n', 1)
text = text.replace('            "--json" in raw_args,\n',
                    '            _has_cli_option(raw_args, {"--json"}),\n', 1)
needle = '    value_positions = _option_value_positions(raw_args)\n'
first = text.index(needle)
second = text.index(needle, first + len(needle))
text = text[:second] + text[second:].replace(needle, '', 1)
text = text.replace('or any(token in ("-h", "--help") for token in clean_before):',
                    'or _has_cli_option(clean_before, {"-h", "--help"}):', 1)
cli_path.write_text(text, encoding='utf-8')
print(json.dumps({'draft': str(draft), 'paths': len(paths)}))
