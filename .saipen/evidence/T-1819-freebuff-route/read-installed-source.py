"""Read selected verified files from the installed Desktop ASAR; never modify it."""
import hashlib
import json
import struct
import sys
from pathlib import Path

archive = Path("C:/Users/vac34/AppData/Local/Programs/@codebufffreebuff-desktop/resources/app.asar")
destination = Path(__file__).resolve().parent / "installed-source"
with archive.open("rb") as source:
    fixed = source.read(16)
    marker, header_size, pickle_size, json_size = struct.unpack("<4I", fixed)
    assert marker == 4 and json_size <= pickle_size <= header_size <= 8 * 1024 * 1024
    header = json.loads(source.read(json_size))
    offset = 8 + header_size
    def lookup(name):
        node = header
        for component in name.split("/"):
            assert component not in ("", ".", "..")
            node = node["files"][component]
        return node
    if sys.argv[1:] == ["--list"]:
        def walk(node, prefix=""):
            for name, entry in node["files"].items():
                full = prefix + name
                if "files" in entry:
                    if full in ("electron", "src") or prefix.startswith(("electron/", "src/")):
                        walk(entry, full + "/")
                else:
                    print(full, entry.get("size"))
        walk(header)
    else:
        destination.mkdir(parents=True, exist_ok=True)
        manifest_path = destination.parent / "installed-source-manifest.json"
        manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {
            "archive": str(archive), "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            "source_version": "0.0.182", "installed_files_read_only": True, "files": {},
        }
        for name in sys.argv[1:]:
            entry = lookup(name)
            assert "link" not in entry and not entry.get("unpacked") and entry["size"] <= 5 * 1024 * 1024
            target = destination / name
            assert target.resolve().is_relative_to(destination.resolve())
            source.seek(offset + int(entry["offset"]))
            raw = source.read(entry["size"])
            digest = hashlib.sha256(raw).hexdigest()
            assert len(raw) == entry["size"] and digest == entry["integrity"]["hash"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            manifest["files"][name] = {"size": len(raw), "sha256": digest}
            print(json.dumps({"path": name, **manifest["files"][name]}))
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
