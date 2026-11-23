import json, collections, datetime
rows = []
for line in open(r"C:/Users/vac34/.saipen/authority/broker.log", encoding="utf-8", errors="replace"):
    line = line.strip()
    if not line.startswith("{"):
        continue
    try:
        rows.append(json.loads(line))
    except ValueError:
        pass

by = collections.defaultdict(list)
for d in rows:
    by[d.get("step")].append(d.get("at"))

for step, times in sorted(by.items(), key=lambda kv: max(kv[1])):
    times = [t for t in times if t]
    print(f"{step:24} n={len(times):4}  min={min(times)}  max={max(times)}")

print()
print("=== last 25 refusals, chronological ===")
for d in rows[-25:]:
    print(d.get("at"), d.get("step"), d.get("op"), d.get("host"), "|", " ".join(d.get("chain") or []))
