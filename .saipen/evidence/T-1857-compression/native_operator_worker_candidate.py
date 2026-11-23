"""UNDEPLOYED entry proposed for tools/native_operator_worker.py."""
import argparse

from saipen_engine.native_delivery import worker_main


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    options = parser.parse_args()
    raise SystemExit(worker_main(options.project_root))
