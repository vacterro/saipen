"""One shard of the declared core-unit discovery (T-1472).

    python -B <engine>/core_unit_shard.py START PATTERN SPEC MANIFEST

Run from a project root. It is ``python -m unittest discover -s START -p
PATTERN -v`` with ONE difference: after the whole discovery, only the tests of
this shard's modules are kept. ``SPEC`` is a JSON file holding either
``{"include": [module, ...]}`` or, for the one catch-all shard,
``{"exclude": [module, ...]}`` -- every module no other shard names, so a module
nobody planned for still runs. ``MANIFEST`` receives what the parent needs to
prove the shards covered the family: the size of the whole discovery, how many
tests this shard kept, and where its time went, per module.

The loader, runner, verbosity, warnings and exit code are unittest's own
(``unittest.main``); the stream a shard writes parses exactly like the
sequential run's. Stdlib only, and nothing here imports the engine: the
sandbox's own modules are the subject.
"""

import os
import sys

# `python -m unittest` puts the working directory first on sys.path; a script
# gets its own directory there instead. Restore the first before any import
# can resolve against this package's modules.
sys.path[0] = os.getcwd()

import json  # noqa: E402
import hashlib  # noqa: E402
import time  # noqa: E402
import unittest  # noqa: E402
import unittest.loader  # noqa: E402


def module_of(test) -> str:
    """The module a test was discovered from; a module that failed to import
    is carried by a ``_FailedTest`` named after it."""
    if isinstance(test, unittest.loader._FailedTest):
        return test._testMethodName
    return type(test).__module__


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def main(argv: list[str]) -> None:
    start, pattern, spec_path, manifest_path = argv
    with open(spec_path, encoding="utf-8") as handle:
        spec = json.load(handle)
    include = set(spec.get("include") or ())
    exclude = set(spec.get("exclude") or ())
    catch_all = "exclude" in spec
    manifest: dict = {"discovered": None, "selected": None, "modules": {}}

    def keep(test) -> bool:
        if spec.get("include_import_errors") and isinstance(test, unittest.loader._FailedTest):
            return True
        module = module_of(test)
        return module not in exclude if catch_all else module in include

    durations = manifest["modules"]

    def write_manifest() -> None:
        for module, seconds in durations.items():
            durations[module] = round(seconds, 3)
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=1, sort_keys=True)

    class ShardLoader(unittest.TestLoader):
        def discover(self, start_dir, pattern="test*.py", top_level_dir=None):
            began = time.perf_counter()
            whole = super().discover(start_dir, pattern, top_level_dir)
            tests = list(flatten(whole))
            # Discovery order is kept, so class and module fixtures run exactly
            # as they do in the sequential run.
            indices = [index for index, test in enumerate(tests) if keep(test)]
            kept = [tests[index] for index in indices]
            manifest["discovered"] = len(tests)
            manifest["selected"] = len(kept)
            # Positions preserve canonical multiplicity when discovery imports
            # the same TestCase through multiple modules. Counts alone allow a
            # duplicate in one shard to conceal an omission in another.
            inventory = [(test.id(), module_of(test)) for test in tests]
            manifest["inventory_sha256"] = hashlib.sha256(
                json.dumps(inventory, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            manifest["selected_indices"] = indices
            if spec.get("include_import_errors"):
                manifest["requested_modules"] = sorted(include)
                manifest["inventory"] = inventory
                manifest["import_error_indices"] = [index for index, test in enumerate(tests)
                    if isinstance(test, unittest.loader._FailedTest)]
                expected_paths = spec.get("expected_module_paths") or {}
                origins, origin_errors = {}, []
                for module, expected_path in expected_paths.items():
                    observed = getattr(sys.modules.get(module), "__file__", None)
                    if observed is not None:
                        normalized = os.path.realpath(observed)
                        relative = os.path.relpath(normalized, os.getcwd())
                        origins[module] = relative.replace("\\", "/")
                        if os.path.normcase(normalized) == os.path.normcase(
                                os.path.realpath(expected_path)):
                            continue
                    origin_errors.append(f"{module}: expected {expected_path}, observed {observed}")
                manifest["expected_module_paths"] = expected_paths
                manifest["module_origins"] = origins
                manifest["dependency_origin_errors"] = origin_errors
                manifest["selected_modules"] = sorted({module_of(test) for test in kept})
                manifest["import_error_modules"] = sorted({module_of(test) for test in kept
                    if isinstance(test, unittest.loader._FailedTest)})
            manifest["discovery_s"] = round(time.perf_counter() - began, 6)
            # Written now too: a shard killed mid-run still tells what it held.
            write_manifest()
            if (spec.get("include_import_errors") and origin_errors
                    and not manifest["import_error_indices"]):
                raise RuntimeError("impact dependency origin mismatch: " + "; ".join(origin_errors))
            return self.suiteClass(kept)

    class TimingResult(unittest.TextTestResult):
        # The time between two tests belongs to the next one's module: that is
        # where setUpModule/setUpClass run.
        _mark = None

        def startTest(self, test):
            now = time.perf_counter()
            if self._mark is None:
                self._mark = now
            self._module = module_of(test)
            durations[self._module] = durations.get(self._module, 0.0) + now - self._mark
            self._mark = now
            super().startTest(test)

        def stopTest(self, test):
            super().stopTest(test)
            now = time.perf_counter()
            durations[self._module] = durations.get(self._module, 0.0) + now - self._mark
            self._mark = now

    class TimingRunner(unittest.TextTestRunner):
        resultclass = TimingResult

        def run(self, test):
            try:
                return super().run(test)
            finally:
                write_manifest()

    unittest.main(
        module=None,
        argv=["python -m unittest", "discover", "-s", start, "-p", pattern, "-v"],
        testLoader=ShardLoader(),
        testRunner=TimingRunner,
    )


if __name__ == "__main__":
    main(sys.argv[1:])
