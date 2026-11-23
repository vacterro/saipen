"""T-1743 F5b: projected_homes expands registry surfaces against the
installer's explicit environment, like every other install decision."""
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
    '''def projected_homes(origin: Path | str) -> list[str]:''',
    '''def _expand_surface(surface: str, env: dict | None) -> str | None:
    """A registry skill surface for the installing account, or None when it
    names a variable this environment does not set (no path on this host)."""
    names = os.environ if env is None else env
    text = surface
    if text.startswith("~"):
        profile = names.get("USERPROFILE") or names.get("HOME")
        if not profile:
            return None
        text = profile + text[1:]

    def value(match: re.Match) -> str:
        found = names.get(match.group(1) or match.group(2) or match.group(3))
        return found if found is not None else match.group(0)

    text = re.sub(r"\\$\\{(\\w+)\\}|\\$(\\w+)|%(\\w+)%", value, text)
    return None if "$" in text or re.search(r"%\\w+%", text) else text


def projected_homes(origin: Path | str, env: dict | None = None) -> list[str]:''',
)
edit(
    "machine_runtime.py",
    '''            if not isinstance(surface, str) or os.path.expandvars(surface).startswith("$"):
                continue
            home = Path(os.path.expandvars(os.path.expanduser(surface)))
''',
    '''            expanded = _expand_surface(surface, env) if isinstance(surface, str) else None
            if not expanded:
                continue
            home = Path(expanded)
''',
)
edit(
    "machine_runtime.py",
    '''            "projected_homes": projected_homes(origin),''',
    '''            "projected_homes": projected_homes(origin, env),''',
)

if __name__ == "__main__":
    base.apply()
