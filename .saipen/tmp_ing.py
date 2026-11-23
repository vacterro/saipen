import json, pathlib, os, datetime

d = pathlib.Path(".saipen/cache/ingress")
for f in sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
    try:
        j = json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        continue
    mt = datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    seal = j.get("seal") or {}
    print(f"{mt}  {f.name:32} size={f.stat().st_size:5} host={j.get('host')!r:12} "
          f"sealed={j.get('sealed')} auth={j.get('authenticated')} "
          f"stage={seal.get('stage')} code={seal.get('code')}")
