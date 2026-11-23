"""T-1743 F6: a pointer into ANY generation directory of the registered
machine runtime follows the CURRENT generation.

Measured: SUNO_DOWNLOADER recorded STATE.saipen_home =
C:/ProgramData/SAI/SAIPEN/runtime/2bd10cc421aacf6a (what `rebind-home --auto`
records when the executing engine is the machine runtime). The install keeps
only the current and previous generation, so the next upgrade deleted that
directory: every write became HOME_REQUIRED, the named cure re-recorded the
then-current generation, and the next upgrade broke it again.
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
    '''def projects(registration: dict | None, home: object) -> bool:''',
    '''def current_generation_for(home: object, env: dict | None = None) -> Path | None:
    """The CURRENT generation directory when `home` names any generation
    directory of the registered machine runtime, else None (T-1743).

    Generation directories are versions of one stable install: the root's
    registration says which is current and older ones are pruned on upgrade.
    A project that recorded one of them recorded the machine runtime, not a
    version of it, so it follows the registration instead of dying with it.
    """
    text = str(home or "").strip()
    if not text:
        return None
    root = default_root(env)
    registration = read_registration(root)
    if root is None or registration is None:
        return None
    try:
        parent = Path(os.path.abspath(text)).parent
    except (OSError, ValueError):
        return None
    if not _same_dir(parent, Path(root) / RUNTIME_DIR):
        return None
    current = runtime_home(root, registration)
    return current if current.is_dir() else None


def projects(registration: dict | None, home: object) -> bool:''',
)
edit(
    "machine_runtime.py",
    '''    if not (recorded and wanted):
        return False
    if _same_dir(recorded, wanted):
        return True
''',
    '''    if not (recorded and wanted):
        return False
    if _same_dir(recorded, wanted):
        return True
    root = str((registration or {}).get("root") or "").strip()
    if root and _same_dir(Path(os.path.abspath(wanted)).parent, Path(root) / RUNTIME_DIR):
        # One of this runtime's own generations (current_generation_for).
        return True
''',
)
edit(
    "state.py",
    '''    text = str(home).strip()
    path = Path(text)
    if not is_absolute_home(text):
        return HOME_UNVERIFIABLE, None
    denied = (''',
    '''    text = str(home).strip()
    path = Path(text)
    if not is_absolute_home(text):
        return HOME_UNVERIFIABLE, None
    from . import machine_runtime

    # A recorded machine-runtime generation is the machine runtime: it is
    # judged as the current generation, never as a pruned directory (T-1743).
    path = machine_runtime.current_generation_for(text) or path
    denied = (''',
)

if __name__ == "__main__":
    base.apply()
