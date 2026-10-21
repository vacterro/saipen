"""Compile the canonical host taxonomy into the self-contained native plugin.

The installed OpenCode plugin must still decide an integration gap when Python
or the skill runtime is missing. This checked facet contains decisions computed
by host_taxonomy; it is not a second policy owner. Regenerate with
`python -m saipen_engine.native_host_policy --write` from tools/.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from . import host_taxonomy as taxonomy
from . import paths

BEGIN = "// BEGIN GENERATED HOST-INTEGRATION-01 POLICY"
END = "// END GENERATED HOST-INTEGRATION-01 POLICY"
GAP_CODES = {
    "SAIPEN_GUARD_UNINSTALLED": "ENGINE_UNREACHABLE",
    "SAIPEN_GUARD_UNREACHABLE": "ENGINE_UNREACHABLE",
    "PLUGIN_RESTART_REQUIRED": "PLUGIN_RESTART_REQUIRED",
}


def facet() -> dict:
    """Closed data read by the native transport without an interpreter."""
    placeholder = "lineage-" + "f" * 32
    canonical_identity = re.escape(paths.identity_file_content(placeholder))
    canonical_identity = canonical_identity.replace(
        re.escape(placeholder), "(lineage-[0-9a-f]{32})"
    )
    canonical_identity = canonical_identity.replace("\\\n", "\\r?\\n")
    return {
        "version": 1,
        "default_mode": taxonomy.DEFAULT_MODE,
        "strict_mode": taxonomy.MODE_STRICT,
        "aliases": taxonomy.MODE_ALIASES,
        "labels": taxonomy.MODE_LABELS,
        "gap_codes": GAP_CODES,
        "identity_observation": {
            "root_env": paths.ENV_PROJECT_ROOT,
            "lineage_env": paths.ENV_PROJECT_LINEAGE,
            "memory_dir": paths.SAIPEN_DIR,
            "identity_file": paths.IDENTITY_NAME,
            "canonical_pattern": "^" + canonical_identity + "$",
            "max_bytes": 4096,
        },
        "failures": {
            code: {
                "decisions": {
                    mode: taxonomy.decide(mode, [{"code": code}])
                    for mode in taxonomy.MODES
                },
                "operator_action": taxonomy.get(code).operator_action,
            }
            for code in taxonomy.codes()
        },
    }


def fragment() -> str:
    return (
        BEGIN + "\nconst HOST_INTEGRATION_POLICY = "
        + json.dumps(facet(), indent=2, ensure_ascii=False)
        + ";\n" + END
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--plugin", type=Path)
    args = parser.parse_args()
    plugin = args.plugin or (
        Path(__file__).resolve().parents[2]
        / "extensions/adapters/opencode/saipen-guard.js"
    )
    text = plugin.read_text(encoding="utf-8")
    first = text.index(BEGIN)
    last = text.index(END, first) + len(END)
    expected = fragment()
    matches = text[first:last] == expected
    if args.write and not matches:
        plugin.write_text(text[:first] + expected + text[last:], encoding="utf-8")
        matches = True
    print(json.dumps({"ok": matches, "plugin": str(plugin)}))
    return 0 if matches else 1


if __name__ == "__main__":
    raise SystemExit(main())
