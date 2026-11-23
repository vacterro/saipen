"""Read-only diagnosis of the actual FastPrompter resolver using disposable roots."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    project = Path(sys.argv[1]).resolve()
    output = Path(sys.argv[2]).resolve()
    sys.path.insert(0, str(project / "src"))
    from fastprompter.utils import paths

    with tempfile.TemporaryDirectory(prefix="fp-audio-reconnect-") as temporary:
        sandbox = Path(temporary)
        # Avoid get_data_dir's writable-directory probe against the live profile.
        paths.get_data_dir = lambda: str(sandbox)
        from fastprompter.core import sound_library

        (sandbox / "personal_audio.json").write_text(
            json.dumps({"personal_override": True, "overrides": {}}), encoding="utf-8"
        )
        builtin, managed, addon = [sandbox / name for name in ("builtin", "managed", "addon")]
        for root in (builtin, managed, addon):
            root.mkdir()
        (builtin / "reconnect.wav").write_bytes(b"disposable bundled fallback fixture")
        kwargs = {"builtin_root": str(builtin), "user_root": str(managed), "addon_root_path": str(addon)}
        before = sound_library.resolve_sound_ref("reconnect.wav", **kwargs)
        (addon / "reconnect.wav").write_bytes(b"disposable personal fixture")
        after = sound_library.resolve_sound_ref("reconnect.wav", **kwargs)
        expected = str(addon / "reconnect.wav")
        record = {
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "kind": "isolated_actual_resolver_probe",
            "subject": str(Path(sound_library.__file__).resolve()),
            "subject_sha256": hashlib.sha256(Path(sound_library.__file__).read_bytes()).hexdigest(),
            "personal_mode": sound_library.personal_audio_enabled(),
            "initial_resolution_is_bundled": before == str(builtin / "reconnect.wav"),
            "after_personal_reconnect_is_personal": after == expected,
            "defect_reproduced": before == after and after != expected,
            "live_configuration_accessed": False,
            "live_configuration_written": False,
            "fixture_audio_claimed_as_original": False,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
