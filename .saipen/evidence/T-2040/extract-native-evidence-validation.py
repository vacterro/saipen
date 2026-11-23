from __future__ import annotations

import ast
import hashlib
import json
import shutil
import textwrap
from pathlib import Path

root = Path.cwd()
path = root / 'tools/saipen_engine/intake.py'
raw = path.read_bytes()
newline = '\r\n' if b'\r\n' in raw else '\n'
text = raw.decode('utf-8').replace('\r\n', '\n')
start = text.index('            if disposition in TERMINAL_DISPOSITIONS and entry.get("actionable", True):\n', text.index('def set_disposition('))
end = text.index('            entry["disposition"] = disposition\n', start)
block = textwrap.dedent(text[start:end])
block = block.replace('        contract = _read_contract(root, receipt_id) or {}\n', '')
block = block.replace('        meta = _read_meta(root, receipt_id) or {}\n', '')
assert '_read_contract(' not in block and '_read_meta(' not in block
helper = (
    'def _disposition_evidence_refusal(\n'
    '    root: Path, receipt_id: str, rid: str, disposition: str, *, entry: dict,\n'
    '    contract: dict, meta: dict, work: str | None, evidence: str | None,\n'
    '    verification: str | None, environment: str | None = None,\n'
    ') -> dict | None:\n'
    '    """Validate a coverage proposal without writing its Source or execution proof."""\n'
    + textwrap.indent(block, '    ')
    + '    return None\n\n\n'
)
replacement = (
    '            refusal = _disposition_evidence_refusal(\n'
    '                root, receipt_id, rid, disposition, entry=entry,\n'
    '                contract=_read_contract(root, receipt_id) or {},\n'
    '                meta=_read_meta(root, receipt_id) or {}, work=work, evidence=evidence,\n'
    '                verification=verification, environment=environment,\n'
    '            )\n'
    '            if refusal:\n'
    '                return refusal\n\n'
)
new = text[:start] + replacement + text[end:]
new = new.replace('def set_disposition(\n', helper + 'def set_disposition(\n', 1)
ast.parse(new)
backup = root / '.saipen/evidence/T-2040/evidence-validation-before'
backup.mkdir(parents=True, exist_ok=False)
shutil.copyfile(path, backup / 'intake.py')
(backup / 'snapshot.json').write_text(json.dumps({'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest()}, indent=2) + '\n', encoding='utf-8', newline='\n')
assert path.read_bytes() == raw
path.write_bytes(new.replace('\n', newline).encode('utf-8'))
print(json.dumps({'before': hashlib.sha256(raw).hexdigest(), 'after': hashlib.sha256(path.read_bytes()).hexdigest(), 'moved_lines': len(block.splitlines())}))
