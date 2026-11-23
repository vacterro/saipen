"""Cross-account readiness matrix through the installed SAI Accounts engine.

Every row is measured by the named account's own broker token. Positive rows
are granted projects; negative rows are paths the account must NOT reach.
"""
import json
import pathlib
import subprocess
import sys

ENGINE = r"C:\ProgramData\SAI\Accounts\bin\sai-accounts.exe"
HERE = pathlib.Path(__file__).resolve().parent

MATRIX = [
    # (label, account, workdir, expectation)
    ("ag3-smart", "AG3", r"V:\___VAC\__K\__CODE\_PY\_SMART_VAC_CLEANER", "READY"),
    ("ag3-suno", "AG3", r"V:\___VAC\__K\__CODE\_TAMPERMONKEY\_SUNO_DOWNLOADER", "ACCESS_OK"),
    ("ag2-suno", "AG2", r"V:\___VAC\__K\__CODE\_TAMPERMONKEY\_SUNO_DOWNLOADER", "ACCESS_OK"),
    ("ag2-smart", "AG2", r"V:\___VAC\__K\__CODE\_PY\_SMART_VAC_CLEANER", "ACCESS_OK"),
    ("ag2-audapack-recovery-ungranted", "AG2", r"V:\___VAC\__K\__CODE\_PY\_AUDAPACK_RECOVERY_20261010", "DENIED"),
    ("ag3-fastprompter-ungranted", "AG3", r"V:\___VAC\__K\__CODE\_PY\_FastPrompter", "DENIED"),
    ("ag3-ag2-profile", "AG3", r"C:\Users\antigravity_b", "DENIED"),
    ("ag2-ag3-profile", "AG2", r"C:\Users\SAIAG_9fabb0d5", "DENIED"),
    ("ag3-operator-profile", "AG3", r"C:\Users\vac34", "DENIED"),
    ("ag3-operator-saipen-home", "AG3", r"C:\Users\vac34\.agents\skills\saipen", "DENIED"),
    ("ag3-machine-runtime-root", "AG3", r"C:\ProgramData\SAI\SAIPEN", "READ_ONLY"),
]


def main() -> int:
    rows = []
    for label, account, workdir, expect in MATRIX:
        proc = subprocess.run(
            [ENGINE, "saipen-readiness", account, "--workdir", workdir],
            capture_output=True, text=True, encoding="utf-8", timeout=900,
        )
        out = proc.stdout.strip()
        (HERE / f"matrix-{label}.json").write_text(out + "\n", encoding="utf-8")
        try:
            d = json.loads(out)
        except ValueError:
            rows.append({"label": label, "expect": expect, "result": "UNPARSEABLE", "rc": proc.returncode})
            continue
        f = d.get("facts") or {}
        access = f.get("project_access") or {}
        adm = f.get("project_admission") or {}
        host = f.get("host_launch") or {}
        rows.append({
            "label": label,
            "account": account,
            "expect": expect,
            "verdict": d.get("verdict"),
            "token_user": host.get("effective_user"),
            "token_sid_matches": host.get("token_matches_account"),
            "access": access.get("status"),
            "access_reason": access.get("reason") or access.get("error"),
            "admission": adm.get("state"),
            "admission_detail": adm.get("error") or adm.get("next_action"),
            "rc": proc.returncode,
        })
    (HERE / "matrix-summary.json").write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    for r in rows:
        print(json.dumps(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
