import importlib.util
import runpy
import sys
from pathlib import Path
scratch = Path(__file__).resolve().parents[2]
root = scratch.parents[2]
sys.path.insert(0, str(root / "tools"))
import saipen_engine
spec = importlib.util.spec_from_file_location("saipen_engine.cold_recovery", scratch / "cold_recovery.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
runpy.run_path(str(root / "tools/saipen.py"), run_name="__main__")
