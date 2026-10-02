"""Real installed OpenCode host, deterministic local model transport.

Only model output is scripted. Native plugin discovery, before-tool hooks,
guard subprocesses, host tool executors and file effects are unmodified.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
from test_guard_hostile_matrix import fresh_project

root = Path(tempfile.mkdtemp(prefix="t1317-opencode-native-"))
shutil.copytree(fresh_project(), root, dirs_exist_ok=True)
before = (root / ".saipen/STATE.md").read_bytes()
records = []

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        names = [t.get("function", {}).get("name") for t in request.get("tools", [])]
        prior = [m for m in request.get("messages", []) if m.get("role") == "tool"]
        index = len(prior)
        records.append({"path": self.path, "tools": names, "prior_tools": prior})
        message = {"role": "assistant", "content": "Smoke complete."}
        finish = "stop"
        if names and index < 2:
            name = "write"
            args = {"filePath": "allowed-smoke.txt" if index == 0 else ".saipen/STATE.md",
                    "content": "ALLOWED" if index == 0 else "BLOCKED-SENTINEL"}
            message = {"role": "assistant", "content": None, "tool_calls": [{
                "index": 0, "id": "call_smoke_" + str(index), "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)}}]}
            finish = "tool_calls"
        base = {"id": "chatcmpl-smoke", "object": "chat.completion", "created": 1,
                "model": "smoke", "usage": {"prompt_tokens": 1, "completion_tokens": 1,
                                               "total_tokens": 2}}
        self.send_response(200)
        if request.get("stream"):
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            chunk = {**base, "object": "chat.completion.chunk", "choices": [{
                "index": 0, "delta": message, "finish_reason": None}]}
            final = {**base, "object": "chat.completion.chunk", "choices": [{
                "index": 0, "delta": {}, "finish_reason": finish}]}
            for item in (chunk, final):
                self.wfile.write(("data: " + json.dumps(item) + "\n\n").encode())
            self.wfile.write(b"data: [DONE]\n\n")
        else:
            payload = json.dumps({**base, "choices": [{"index": 0, "message": message,
                                                      "finish_reason": finish}]}).encode()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
config = {"provider": {"saipen-smoke": {"npm": "@ai-sdk/openai-compatible",
          "name": "Local deterministic enforcement test", "options": {
              "baseURL": f"http://127.0.0.1:{server.server_port}/v1", "apiKey": "local-fixture"},
          "models": {"smoke": {"name": "smoke"}}}}, "permission": "allow",
          "mcp": {"codebase-memory-mcp": {"enabled": False}}}
env = {**os.environ, "SAIPEN_AGENT": "test-agent", "SAIPEN_SKILL_ROOT": str(REPO),
       "SAIPEN_GUARD_STARTUP_PROBE": str(root / "startup-probe.txt"),
       "OPENCODE_CONFIG_CONTENT": json.dumps(config)}
binary = Path(shutil.which("opencode")).parent / "node_modules/opencode-ai/bin/opencode.exe"
out = REPO / ".saipen/kitchen/t1317-opencode-provider"
try:
    p = subprocess.run([str(binary), "run", "--print-logs", "--agent", "build",
                        "--model", "saipen-smoke/smoke", "--format", "json",
                        "Run isolated enforcement fixture."], cwd=root, env=env,
                       capture_output=True, timeout=90)
    code, stdout, stderr = p.returncode, p.stdout, p.stderr
except subprocess.TimeoutExpired as exc:
    code, stdout, stderr = "TIMEOUT", exc.stdout or b"", exc.stderr or b""
finally:
    server.shutdown()
out.with_suffix(".stdout").write_bytes(stdout)
out.with_suffix(".stderr").write_bytes(stderr)
report = {"fixture": str(root), "exit": code, "requests": records,
          "factory_probe": (root / "startup-probe.txt").exists(),
          "allowed_effect": (root / "allowed-smoke.txt").exists(),
          "protected_bytes_unchanged": (root / ".saipen/STATE.md").read_bytes() == before}
out.with_suffix(".json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps({k: v for k, v in report.items() if k != "requests"}))
