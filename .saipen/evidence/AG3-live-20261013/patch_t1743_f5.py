"""T-1743 F5: the machine runtime serves every agent home the installing
operator proved was projected from the same source.

Measured: SMART_VAC_CLEANER records STATE.saipen_home
C:\\Users\\vac34\\.agents\\skills\\saipen, an injector projection of the SAIPEN
checkout, while the machine runtime records source_root = the checkout. A
path comparison called that "another install", so AG3 could READ the project
but every lifecycle WRITE was refused with "This needs the operator".
"""
import importlib.util
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("p1743", HERE / "patch_t1743.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.EDITS.clear()
edit = base.edit

edit(
    "machine_runtime.py",
    '''def projects(registration: dict | None, home: object) -> bool:
    """Was this machine runtime projected from `home`?

    A machine runtime stands in for ONE install: the one it was projected
    from. A project whose recorded home is some other install is not this
    runtime's to serve -- that would be a substitution, whatever the versions
    say. A comparison of two recorded paths: the home itself is, by the very
    case this exists for, unreadable.
    """
    recorded = str((registration or {}).get("source_root") or "").strip()
    wanted = str(home or "").strip()
    return bool(recorded) and bool(wanted) and _same_dir(recorded, wanted)
''',
    '''def projects(registration: dict | None, home: object) -> bool:
    """Was this machine runtime projected from `home`?

    A machine runtime stands in for ONE source: the install it was projected
    from, and the agent homes the installing operator proved at install time
    are projections of that same source (`projected_homes`, T-1743). A
    project whose recorded home is some other install is not this runtime's
    to serve -- that would be a substitution, whatever the versions say. A
    comparison of recorded paths: the home itself is, by the very case this
    exists for, unreadable.
    """
    recorded = str((registration or {}).get("source_root") or "").strip()
    wanted = str(home or "").strip()
    if not (recorded and wanted):
        return False
    if _same_dir(recorded, wanted):
        return True
    homes = (registration or {}).get("projected_homes") or ()
    return isinstance(homes, list) and any(
        isinstance(item, str) and item.strip() and _same_dir(item, wanted) for item in homes
    )


def projected_homes(origin: Path | str) -> list[str]:
    """The agent homes the installing account can PROVE follow `origin`.

    A home qualifies only when it is one of the adapter registry's declared
    skill surfaces for this account AND its own install stamp
    (`.saipen_runtime.json`) names `origin` as its canonical source. Read by
    the operator at install time -- the one moment an account that can read
    those homes is present -- so a managed account that cannot read them later
    can still be told, truthfully, that this runtime serves them.
    """
    source = Path(origin)
    try:
        registry = json.loads(
            (source / "extensions" / "adapters" / "registry.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return []
    found: dict[str, str] = {}
    for adapter in registry.get("adapters") or []:
        for surface in (adapter or {}).get("skill_surfaces") or []:
            if not isinstance(surface, str) or os.path.expandvars(surface).startswith("$"):
                continue
            home = Path(os.path.expandvars(os.path.expanduser(surface)))
            try:
                stamp = json.loads((home / ".saipen_runtime.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            declared = str((stamp or {}).get("canonical_source_root") or "").strip()
            if declared and _same_dir(declared, source) and not _same_dir(home, source):
                found.setdefault(os.path.normcase(os.path.abspath(home)), os.path.abspath(home))
    return sorted(found.values())
''',
)
edit(
    "machine_runtime.py",
    '''            "source_root": os.path.abspath(str(origin)),
            "previous": (''',
    '''            "source_root": os.path.abspath(str(origin)),
            # T-1743: injector homes proven to follow the same source; the
            # projects() test serves a project that records one of them.
            "projected_homes": projected_homes(origin),
            "previous": (''',
)
edit(
    "host_bootstrap.py",
    '''                result["binding"]["legacy_saipen_home"] = (
                    "INACCESSIBLE_BUT_REPLACED"
                    if machine_runtime.projects(machine, persisted_value)
                    else "INACCESSIBLE_NOT_THIS_RUNTIME"
                )
''',
    '''                replaced = machine_runtime.projects(machine, persisted_value)
                result["binding"]["legacy_saipen_home"] = (
                    "INACCESSIBLE_BUT_REPLACED" if replaced else "INACCESSIBLE_NOT_THIS_RUNTIME"
                )
                if replaced:
                    # Nothing is owed: the remedy text written for an unknown
                    # home would send an agent to ask for an action that the
                    # running runtime has already taken (T-1743).
                    result["binding"]["reason"] = (
                        f"STATE.saipen_home {persisted_value!r} is not readable by this "
                        f"account; the machine runtime {machine.get('root')} serves this "
                        "project in its place. No operator action is needed"
                    )
''',
)

if __name__ == "__main__":
    base.apply()
