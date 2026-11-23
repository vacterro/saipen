"""Isolated before/after control for the FastPrompter reconnect cache defect.

T-1924 requires the reconnect cache defect to have an isolated before/after
control. This runs the ACTUAL resolver (never a copy of its rules) against
disposable roots in a temporary directory, and measures both arms of one
discriminating variable:

  RED    the resolver cache is left alone across the appearance of a
         higher-priority personal file, so the cached bundled fallback wins;
  GREEN  the same sequence with only `_RESOLVE_CACHE` cleared before the
         second resolution, so the personal file wins.

The two arms differ in exactly one step. If the cache were innocent, both
arms would select the personal file; if the roots were the problem, the
green arm would still select the bundled fallback. Selecting bundled in the
red arm and personal in the green arm isolates the cache as the cause.

Nothing here reads or writes the operator's live profile: `get_data_dir` is
replaced with a temporary directory before the resolver module is imported,
and no original audio is claimed -- the fixtures are bytes this script
writes itself.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REF = "reconnect.wav"
BUNDLED_BYTES = b"disposable bundled fallback fixture"
PERSONAL_BYTES = b"disposable personal fixture"


def _fixture_tree(sandbox: Path):
    builtin = sandbox / "builtin"
    managed = sandbox / "managed"
    addon = sandbox / "addon"
    for root in (builtin, managed, addon):
        root.mkdir()
    (builtin / REF).write_bytes(BUNDLED_BYTES)
    (sandbox / "personal_audio.json").write_text(
        json.dumps({"personal_override": True, "overrides": {}}), encoding="utf-8"
    )
    return builtin, managed, addon


def measure(project: Path) -> dict:
    output: dict = {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "kind": "isolated_before_after_control",
        "live_configuration_accessed": False,
        "live_configuration_written": False,
        "fixture_audio_claimed_as_original": False,
    }
    sys.path.insert(0, str(project / "src"))
    try:
        from fastprompter.utils import paths

        with tempfile.TemporaryDirectory(prefix="fp-audio-control-") as temporary:
            sandbox = Path(temporary)
            # Ordered before the import below: sound_library binds the
            # resolver's default roots at call time, but the personal marker
            # path is computed from get_data_dir per call.
            paths.get_data_dir = lambda: str(sandbox)
            from fastprompter.core import sound_library

            output["subject"] = str(Path(sound_library.__file__).resolve())
            output["subject_sha256"] = hashlib.sha256(
                Path(sound_library.__file__).read_bytes()
            ).hexdigest()

            builtin, managed, addon = _fixture_tree(sandbox)
            kwargs = {
                "builtin_root": str(builtin),
                "user_root": str(managed),
                "addon_root_path": str(addon),
            }
            personal_path = str(addon / REF)
            bundled_path = str(builtin / REF)

            # --- RED ARM: cache untouched ---------------------------------
            sound_library._RESOLVE_CACHE.clear()
            sound_library.invalidate_personal_audio_cache()
            red_before = sound_library.resolve_sound_ref(REF, **kwargs)
            (addon / REF).write_bytes(PERSONAL_BYTES)
            red_after = sound_library.resolve_sound_ref(REF, **kwargs)

            # --- GREEN ARM: only the resolver cache is cleared --------------
            # The personal fixture is removed so the green arm starts from
            # the same observable state as the red arm: bundled only. The
            # single difference from the red arm is the cache clear between
            # the two resolutions.
            (addon / REF).unlink()
            sound_library._RESOLVE_CACHE.clear()
            green_before = sound_library.resolve_sound_ref(REF, **kwargs)
            (addon / REF).write_bytes(PERSONAL_BYTES)
            sound_library._RESOLVE_CACHE.clear()
            green_after = sound_library.resolve_sound_ref(REF, **kwargs)

            output["personal_mode"] = sound_library.personal_audio_enabled()
            output["red_arm"] = {
                "initial": red_before == bundled_path and "bundled",
                "after_personal_appears": red_after == personal_path and "personal",
                "selected_path_after": red_after,
                "defect_reproduced": red_after == bundled_path,
            }
            output["green_arm"] = {
                "initial": green_before == bundled_path and "bundled",
                "after_personal_appears": green_after == personal_path and "personal",
                "selected_path_after": green_after,
                "defect_reproduced": green_after == bundled_path,
            }
            output["discriminating_variable"] = "_RESOLVE_CACHE cleared before 2nd resolve"
            output["cache_isolates_cause"] = (
                red_after == bundled_path and green_after == personal_path
            )
            output["cache_key_shape"] = list(sound_library._cache_key(
                REF, str(builtin), str(managed), str(addon)
            ))
            output["cache_key_carries_personal_mode"] = any(
                sound_library.personal_audio_enabled() is part
                for part in sound_library._cache_key(
                    REF, str(builtin), str(managed), str(addon)
                )
            )
    except Exception as exc:  # noqa: BLE001 - the control records its own failure
        output["error"] = f"{type(exc).__name__}: {exc}"
    return output


def main() -> int:
    project = Path(sys.argv[1]).resolve()
    output_path = Path(sys.argv[2]).resolve()
    record = measure(project)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))
    return 0 if record.get("cache_isolates_cause") else 1


if __name__ == "__main__":
    raise SystemExit(main())
