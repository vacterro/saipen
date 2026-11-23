import json

for f in ["ing-101312dc5eacdadd", "ing-a7c1a5691f6ba4ec", "ing-1558edb21c8fe037", "ing-58d51eafb7b56734"]:
    try:
        d = json.load(open(".saipen/cache/ingress/" + f + ".json", encoding="utf-8"))
    except OSError as exc:
        print(f, "ERR", exc)
        continue
    print("==", f)
    for k in ("witness", "declared_by", "destination_op", "consumed", "consumed_by",
              "session_id", "created_at", "message_id"):
        print(f"   {k} = {d.get(k)!r}")
    oo = d.get("operator_origin")
    if isinstance(oo, dict):
        print("   operator_origin keys:", list(oo.keys()))
        print("   operator_origin:", json.dumps(oo)[:600])
    else:
        print("   operator_origin =", oo)
    print()
