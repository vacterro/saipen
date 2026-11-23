import ast, sys
from pathlib import Path
src = Path(sys.argv[1]).read_text(encoding="utf-8")
tree = ast.parse(src)
funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
def calls(node):
    return {c.func.id for c in ast.walk(node) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
def guarded(node):
    return any((isinstance(d, ast.Name) and d.id == "_state_guard") for d in node.decorator_list)
def catches(node):
    for h in ast.walk(node):
        if isinstance(h, ast.ExceptHandler) and h.type is not None:
            names = {n.id for n in ast.walk(h.type) if isinstance(n, ast.Name)}
            if names & {"CheckpointError", "ValueError", "Exception"}:
                return True
    return False
direct = {name for name, node in funcs.items() if "_read" in calls(node)}
unguarded_direct = sorted(n for n in direct if not guarded(funcs[n]))
print("functions calling _read:", len(direct), "| unguarded:", len(unguarded_direct))
callers = {}
for name, node in funcs.items():
    for c in calls(node):
        callers.setdefault(c, set()).add(name)
for n in unguarded_direct:
    ups = sorted(callers.get(n, ()))
    print(f"  {n:38s} line {funcs[n].lineno:6d} catches={catches(funcs[n])} called_by={[(u, guarded(funcs[u])) for u in ups][:5]}")
