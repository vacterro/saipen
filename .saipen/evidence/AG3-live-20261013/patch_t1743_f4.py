"""T-1743 F4: recovery's residue route names the foreign-field compaction."""
import importlib.util
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("p1743", HERE / "patch_t1743.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.EDITS.clear()
base.edit(
    "reconcile.py",
    '''    for marker, command in _RESIDUE_ROUTES:
        if any(marker in item for item in residue):
            return command
    for item in residue:
        match = _STRANDED_TASK_RE.search(item)
''',
    '''    for marker, command in _RESIDUE_ROUTES:
        if any(marker in item for item in residue):
            return command
    # T-1743: a row whose ONLY fault is a field outside the closed grammar has
    # a lossless canonical repair. Naming nothing here was the dead end that
    # left SMART_VAC_CLEANER's every lifecycle verb refused.
    errors = list((board or {}).get("errors") or [])
    if errors:
        from .board_compaction import unrecognized_field_ticket

        foreign = [unrecognized_field_ticket(error) for error in errors]
        if all(foreign):
            return f"saipen ticket compact {foreign[0]}"
    for item in residue:
        match = _STRANDED_TASK_RE.search(item)
''',
)
if __name__ == "__main__":
    base.apply()
