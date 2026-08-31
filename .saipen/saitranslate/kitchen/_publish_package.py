from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

from freshness import compute_role_revision, compute_source_identity  # noqa: E402
from saipen_engine import producer as producer_api  # noqa: E402


def main() -> None:
    namespace = ROOT / ".saipen" / "saitranslate"
    kitchen = namespace / "kitchen"
    charter = ROOT / ".saipen" / "extensions" / "subs" / "saitranslate.md"
    identity = compute_source_identity(ROOT)
    role_revision = compute_role_revision(charter)

    locale_paths = sorted(
        path.relative_to(ROOT).as_posix()
        for path in kitchen.glob("*/README_*.md")
        if path.parent.name != ".translation-cache"
    )
    if len(locale_paths) != 32:
        raise RuntimeError(f"expected 32 locale README payloads, found {len(locale_paths)}")

    mirror_sources = {
        "README.ded.md": kitchen / "ded" / "README_DED.md",
        "README.ee.md": kitchen / "et" / "README_ET.md",
        "README.ja.md": kitchen / "ja" / "README_JA.md",
    }
    write_paths = locale_paths + sorted(mirror_sources)
    read_paths = [
        "README.md",
        "VERSION",
        "SPEC.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "CODE_OF_CONDUCT.md",
        "GUIDE.md",
        "saipen/phases/translate.md",
    ]
    read_paths.extend(
        sorted(path.relative_to(ROOT).as_posix() for path in (ROOT / "guides").glob("GUIDE_*.md"))
    )
    read_paths.extend(sorted(mirror_sources))

    epoch = producer_api.ProducerEpoch.claim(namespace)
    package = producer_api.build_package(
        producer="saitranslate",
        role_revision=role_revision,
        base_source_head=identity.source_head,
        base_source_tree_fingerprint=identity.source_tree_fingerprint,
        base_discovery_model=identity.discovery_model,
        scope="force-fresh-all-real-docs-32-locales-no-ui-v7.231.3",
        read_set=producer_api.read_set_from(ROOT, read_paths),
        write_set=producer_api.write_set_before(ROOT, write_paths),
        epoch=epoch,
        status="ready",
    )
    generation = producer_api.StagingGeneration(namespace, "saitranslate").begin()
    for rel_path in locale_paths:
        generation.add_payload(rel_path, (ROOT / rel_path).read_bytes())
    for rel_path, source in mirror_sources.items():
        generation.add_payload(rel_path, source.read_bytes())
    generation.set_package(package)
    result = generation.publish()
    if not result.get("ok"):
        raise RuntimeError(json.dumps(result, sort_keys=True))
    print(
        json.dumps(
            {
                "epoch": epoch,
                "package_identity": package.package_identity,
                "payload_count": len(write_paths),
                "read_count": len(read_paths),
                "publish": result,
                "role_revision": role_revision,
                "source_head": identity.source_head,
                "source_tree_fingerprint": identity.source_tree_fingerprint,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
