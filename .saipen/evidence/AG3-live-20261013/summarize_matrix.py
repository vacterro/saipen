"""Print one line per readiness record: account, workdir, verdict, access, admission."""
import json
import pathlib
import sys

for name in sys.argv[1:]:
    path = pathlib.Path(name)
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        print(path.stem, "UNPARSEABLE", exc)
        continue
    f = d.get("facts") or {}
    access = f.get("project_access") or {}
    adm = f.get("project_admission") or {}
    host = f.get("host_launch") or {}
    print(
        f"{d.get('compact_label')} {path.stem}: verdict={d.get('verdict')}"
        f" token={host.get('effective_user')}"
        f" access={access.get('status')}/{access.get('reason') or access.get('error')}"
        f" admission={adm.get('state')} {adm.get('error') or adm.get('next_action')}"
    )
