"""Share direct tools modules only when both names resolve to the same file."""

from __future__ import annotations

import importlib
import sys
from importlib.machinery import ModuleSpec, PathFinder
from pathlib import Path
from types import ModuleType


def _same_file(module: ModuleType, source: Path) -> bool:
    origin = getattr(module, "__file__", None)
    if not origin:
        return False
    try:
        return Path(origin).resolve() == source
    except (OSError, ValueError):
        return False


class _ReuseLoader:
    def __init__(self, module: ModuleType) -> None:
        self.module = module
        self.spec = module.__spec__

    def create_module(self, spec: ModuleSpec) -> ModuleType:
        return importlib.import_module(self.module.__name__)

    def exec_module(self, module: ModuleType) -> None:
        module.__spec__ = self.spec

    def get_code(self, fullname: str):
        return self.spec.loader.get_code(self.spec.name)

    def get_filename(self, fullname: str) -> str:
        return self.module.__file__


class _CodeLoader:
    def __init__(self, original) -> None:
        self.original = original

    def create_module(self, spec: ModuleSpec):
        return self.original.create_module(spec)

    def exec_module(self, module: ModuleType) -> None:
        self.original.exec_module(module)

    def get_code(self, fullname: str):
        return self.original.get_code(self.original.name)

    def get_filename(self, fullname: str) -> str:
        return self.original.get_filename(self.original.name)


class _ToolsModuleFinder:
    def __init__(self, directory: Path) -> None:
        self.directory = directory.resolve()

    def _flat_is_owned(self, name: str, source: Path) -> bool:
        loaded = sys.modules.get(name)
        if loaded is not None:
            return _same_file(loaded, source)
        spec = PathFinder.find_spec(name)
        return bool(spec and spec.origin and Path(spec.origin).resolve() == source)

    def find_spec(self, fullname: str, path=None, target=None):
        name = fullname.removeprefix("tools.")
        if not name.isidentifier() or name == "__main__":
            return None
        spec = PathFinder.find_spec(fullname, path)
        source = (self.directory / f"{name}.py").resolve()
        if not spec or not spec.origin or Path(spec.origin).resolve() != source:
            return None
        if target is not None and _same_file(target, source):
            # Reload re-executes the owned source into the existing object;
            # an alias-only loader would silently suppress that execution.
            spec.loader = _CodeLoader(spec.loader)
            return spec
        flat_owned = self._flat_is_owned(name, source)
        if fullname.startswith("tools.") and flat_owned:
            # Both import spellings take the flat module's import lock. A
            # second thread must not execute another object or see its globals
            # before initialization finishes.
            module = importlib.import_module(name)
            return ModuleSpec(fullname, _ReuseLoader(module), origin=spec.origin)
        other = name if fullname.startswith("tools.") else f"tools.{name}"
        if not flat_owned and not other.startswith("tools."):
            return None
        loaded = sys.modules.get(other)
        if loaded is not None and _same_file(loaded, source):
            return ModuleSpec(fullname, _ReuseLoader(loaded), origin=spec.origin)
        spec.loader = _CodeLoader(spec.loader)
        return spec


def install(directory: Path) -> None:
    """Keep executable __main__, engine packages and foreign names separate."""
    directory = directory.resolve()
    if any(isinstance(finder, _ToolsModuleFinder) for finder in sys.meta_path):
        return
    finder = _ToolsModuleFinder(directory)
    sys.meta_path.insert(0, finder)
    package = sys.modules["tools"]
    for name, module in list(sys.modules.items()):
        leaf = name.removeprefix("tools.")
        if not leaf.isidentifier() or leaf == "__main__":
            continue
        source = (directory / f"{leaf}.py").resolve()
        if not _same_file(module, source) or not finder._flat_is_owned(leaf, source):
            continue
        if getattr(module.__spec__, "_initializing", False):
            continue
        dotted = f"tools.{leaf}"
        if dotted not in sys.modules:
            sys.modules[dotted] = module
        if leaf not in sys.modules:
            sys.modules[leaf] = module
        if module.__spec__ is not None and not isinstance(
            module.__spec__.loader, (_CodeLoader, _ReuseLoader),
        ):
            # A cached alias bypasses find_spec. Keep the canonical spec name,
            # while allowing runpy to request code under either public name.
            module.__spec__.loader = _CodeLoader(module.__spec__.loader)
        setattr(package, leaf, module)
