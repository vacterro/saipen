"""Wave B: profile only test_layouts_agree_on_the_live_repository."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import profile_validator_layout_parity as p

def main() -> dict:
    import io, json, unittest
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName(
        "test_validator_layout_parity.InstalledValidatorLayoutParityTests.test_layouts_agree_on_the_live_repository"
    )
    import test_validator_layout_parity as vlp
    module_home = vlp.HOME
    p.current["name"] = "live"
    t0 = p.time.perf_counter()
    import io as _io
    buf = _io.StringIO()
    runner = unittest.TextTestRunner(stream=buf, verbosity=0)
    result = runner.run(suite)
    wall = p.time.perf_counter() - t0
    report = {"wall_s": wall, "ok": result.wasSuccessful(), "phases": p.timings}
    print(json.dumps(report, indent=1))
    return report

main()
