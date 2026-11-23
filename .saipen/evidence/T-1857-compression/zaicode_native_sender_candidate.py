"""UNDEPLOYED callback artifact; no installed/trusted-host claim.

Proposed entry only for genuine accepted native UserPromptSubmit callbacks.
The broker must independently authenticate this exact shipped callback and
the approved ZAICODE issuer; copying the script does not grant that trust.
"""
import argparse
import json
import sys
from pathlib import Path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", choices=("zaicode",), required=True)
    parser.add_argument("--saipen-root", required=True)
    options = parser.parse_args()
    # The canonical installer/native callback owns this argument; no path is
    # selected from the user's text. Runtime compatibility remains T-1854's
    # prerequisite. The broker additionally authenticates shipped artifact bytes.
    sys.path.insert(0, str(Path(options.saipen_root) / "tools"))
    from saipen_engine.native_delivery import MAX_PACKET_BYTES, deliver, refusal

    try:
        raw = sys.stdin.buffer.read(MAX_PACKET_BYTES + 1)
        if len(raw) > MAX_PACKET_BYTES:
            raise ValueError("native callback packet exceeds its declared limit")
        event = json.loads(raw.decode("utf-8"))
        if not isinstance(event, dict) or event.get("host") != options.host:
            raise ValueError("native event host differs from the installed callback")
        result = deliver(event, options.saipen_root)
    except (UnicodeError, ValueError) as error:
        result = refusal(str(error))
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result.get("ok") is True else 1)
