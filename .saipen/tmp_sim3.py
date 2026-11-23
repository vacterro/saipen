import sys, json, pathlib, subprocess
sys.path.insert(0, 'tools')
from pathlib import Path
from saipen_engine import host_authority_broker as B
from saipen_engine import host_authority_identity as H
from saipen_engine.host_authority_process import ProcessFact

cfg = json.loads(pathlib.Path(r"C:\Users\vac34\.zcode\cli\config.json").read_text(encoding="utf-8"))
h = cfg["hooks"]["events"]["UserPromptSubmit"][0]["hooks"][0]
py = h["command"]; args = h["args"]
hookargv = tuple([py] + args)


def fact(pid, ppid, image, argv, created=0):
    base = image.replace(chr(92), "/").rsplit("/", 1)[-1].lower()
    return ProcessFact(pid, ppid, image, base, argv, created)


Z = r"V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_ZAICODE\zcode\packages\desktop\dist\win-unpacked\ZAICODE.exe"
root = Path(r"C:\Users\vac34\.claude\skills\saipen")
br = B.Broker(saipen_root=root, runtime=Path(r"C:\Users\vac34\.saipen\authority"))
home = Path(r"C:\Users\vac34\.zcode")
arts = br._hook_artifacts("zaicode", home)
hc = dict(B.settings(host="zaicode"))
hosts = hc.get("hosts") or {}
hc.update(hosts.get("zaicode") or {})
policy = H.IdentityPolicy(
    host="zaicode",
    host_images=tuple(hc.get("host_images") or ()),
    hook_artifacts=tuple(arts),
    host_signers=(),
    shells=tuple(hc.get("hook_shells") or H.DEFAULT_SHELLS),
    bridge_images=tuple(hc.get("bridge_images") or ()),
    max_shells=int(hc.get("max_shells") or 0),
    max_bridges=int(hc.get("max_bridges") or 2),
    profile_hook=None,
)
print("hook_artifacts:", policy.hook_artifacts)
print("max_shells:", policy.max_shells, "shells:", policy.shells)

chain = [fact(100, 200, py, hookargv), fact(200, 300, Z, ("ZAICODE.exe", "app-server")),
         fact(300, 400, Z, ("ZAICODE.exe", "--type=utility")), fact(400, 1, Z, ("ZAICODE.exe",))]
p1 = H.prove_hook_invocation(chain, policy, signer_of=lambda p: None,
                             artifact_current=lambda s: True, hook_for_host=None, report_limit=8)
print("DIRECT ok:", p1.ok, "reason:", p1.reason, "detail:", p1.detail)

cmd = subprocess.list2cmdline(list(hookargv))
sh = fact(200, 300, r"C:\Program Files\Git\bin\bash.exe", ("bash.exe", "-c", cmd))
chain2 = [fact(100, 200, py, hookargv), sh, fact(300, 1, Z, ("ZAICODE.exe",))]
p2 = H.prove_hook_invocation(chain2, policy, signer_of=lambda p: None,
                             artifact_current=lambda s: True, hook_for_host=None, report_limit=8)
print("SHELL ok:", p2.ok, "reason:", p2.reason, "detail:", p2.detail)
