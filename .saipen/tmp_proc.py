import subprocess

ps = r"""
Get-CimInstance Win32_Process -Filter "name='zaicode.exe'" |
  Select-Object ProcessId,ParentProcessId,CommandLine |
  ConvertTo-Json -Depth 3
"""
p = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                   capture_output=True, text=True, timeout=120)
print(p.stdout[:6000])
print("ERR", p.stderr[:1000])
