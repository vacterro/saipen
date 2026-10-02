from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "tools"))

from freshness import compute_role_revision, compute_source_identity  # noqa: E402
from saipen_engine import producer as producer_api  # noqa: E402


def main() -> None:
    namespace = ROOT / ".saipen" / "extensions" / "subs" / "saiwiki"
    wiki = namespace / "kitchen" / "wiki"
    charter = ROOT / ".saipen" / "extensions" / "subs" / "saiwiki.md"
    identity = compute_source_identity(ROOT)
    role_revision = compute_role_revision(charter)

    page_names = [
        "Getting-Started.md",
        "Home.md",
        "Phases.md",
        "Scenarios.md",
        "SubSaipen.md",
        "Tutorials.md",
        "Use-Cases.md",
        "_Footer.md",
        "_Sidebar.md",
    ]
    write_paths = [
        (wiki / name).relative_to(ROOT).as_posix() for name in page_names
    ]
    read_paths = [
        "CHANGELOG.md",
        "KNOWLEDGE/ADR-0001-v7-producer-parallelism.md",
        "README.md",
        "VERSION",
        "extensions/subs/PROTOCOL.md",
        "extensions/subs/crew.md",
        "extensions/subs/saihunt.md",
        "extensions/subs/saipython.md",
        "extensions/subs/saitest.md",
        "extensions/subs/saitranslate.md",
        "extensions/subs/saiui.md",
        "extensions/subs/saiwiki.md",
        "saipen/BOOT.md",
        "saipen/COMMANDS.md",
        "saipen/CONFORMANCE.md",
        "saipen/CONTROLS.md",
        "saipen/CONVERGE.md",
        "saipen/CORE.md",
        "saipen/OPS.md",
        "saipen/REGISTRY.json",
        "saipen/RUNTIME.md",
        "saipen/SOURCES.md",
        "saipen/STYLE.md",
        "saipen/phases/add.md",
        "saipen/phases/blocked.md",
        "saipen/phases/build.md",
        "saipen/phases/clean.md",
        "saipen/phases/done.md",
        "saipen/phases/hunt.md",
        "saipen/phases/init.md",
        "saipen/phases/markhunt.md",
        "saipen/phases/plan.md",
        "saipen/phases/prepare.md",
        "saipen/phases/review.md",
        "saipen/phases/scout.md",
        "saipen/phases/ship.md",
        "saipen/phases/translate.md",
        "saipen/phases/validate.md",
        "saipen/phases/verify.md",
        "tools/freshness.py",
        "tools/saipen.py",
        "tools/saipen_engine/crew.py",
        "tools/saipen_engine/disposition.py",
        "tools/saipen_engine/effects.py",
        "tools/saipen_engine/intent.py",
        "tools/saipen_engine/journal.py",
        "tools/saipen_engine/producer.py",
        "tools/saipen_engine/release.py",
        "tools/saipen_engine/runtime/__init__.py",
        "tools/saipen_engine/runtime/base.py",
        "tools/saipen_engine/intake.py",
        "tools/saipen_engine/subs.py",
        "tools/userperson.py",
        "tools/validate.py",
    ]
    absent = [path for path in read_paths if not (ROOT / path).is_file()]
    if absent:
        raise RuntimeError(f"missing read dependencies: {absent}")

    epoch = producer_api.ProducerEpoch.claim(namespace)
    package = producer_api.build_package(
        producer="saiwiki",
        role_revision=role_revision,
        base_source_head=identity.source_head,
        base_source_tree_fingerprint=identity.source_tree_fingerprint,
        base_discovery_model=identity.discovery_model,
        scope=(
            "force-fresh-wiki-current-source-triple: transport/telegrams/autonomy/"
            "QUALITY>TIME/supersession/crew-record truth mirrored from BOOT.md, "
            "COMMANDS.md, CORE.md and RUNTIME.md"
        ),
        read_set=producer_api.read_set_from(ROOT, read_paths),
        write_set=producer_api.write_set_before(ROOT, write_paths),
        epoch=epoch,
        status="ready",
    )
    generation = producer_api.StagingGeneration(namespace, "saiwiki").begin()
    for rel_path in write_paths:
        generation.add_payload(rel_path, (ROOT / rel_path).read_bytes())
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
                "publish": result,
                "read_count": len(read_paths),
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
