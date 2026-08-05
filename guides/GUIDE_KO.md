<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# SAIPEN 가이드 (한국어)

SAIPEN은 프로젝트 내 `.saipen/` 폴더에 위치한 AI 에이전트용 지속성 메모장입니다.

**빠른 키:** `cc`는 활성 Goal Mode 실행을 계속하고, `sss`는 코드를 건드리지 않고 상태를 보여주며, `ss`는 체크포인트를 저장하고 멈춥니다. [전체 15 키 맵 보기](../saipen/RFC.md#110-command-surface). 키릴 문자 쌍둥이도 작동합니다: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

## 빠른 시작

1. **머신당 한 번 설치:**
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

2. **프로젝트 시작:**
> `saipen set`

3. **작업:**
> `saipen`

## 명령어

| 명령어 | 동작 |
|---|---|
| `saipen set` | 메모리 폴더 `.saipen/` 초기화 |
| `saipen continue` | 노트에서 작업 재개 |
| `saipen stop` | 진행 상황 저장 및 중지 |
| `saipen status` | 보드 및 상태 읽기 |
| `saipen goal <text>` | 새로운 목표로 전환 |
| `saipen clean` | 저장소 딥 클린 |
| `saipen translate` | 격리된 32개 언어 번역 빌드 |
| `saipen markhunt` | 깊고 무제한적인 감사 -- 발견만 기록, 수정 안 함 |
| `saipen prepare` | 다음 에이전트에게 인계할 작업 패키징 |
| `saipen ship` | 릴리스 플로우 트리거 |

## 알아두면 좋은 것
- 프로젝트로 돌아왔을 때 커밋되지 않은 변경사항이 있다면? 정상입니다 -- SAIPEN은 매 단계가 아니라 `ship` 시점에만 커밋합니다. 에이전트는 무언가를 건드리기 전에 먼저 그 변경사항이 누구의 것인지 확인합니다.
- 실제 아키텍처 결정을 기억하게 하고 싶다면? `.saipen/KNOWLEDGE/`에 `decisions.md` 파일 하나로, 또는 번호가 매겨진 `ADR-001.md` 파일들로 넣으세요.
- 이 머신에 git이나 shell이 없다면? 에이전트는 추측하는 대신 명확하게 말합니다 (`mode`, `WAIT: <category> -- <질문>`). (카테고리는 일곱 가지 중 하나입니다: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; 어떤 종류의 답변이 차단을 해제하는지 알려줍니다)
- 안전망을 원하세요? `python <saipen-클론>/tools/install_hook.py`로 커밋 전 검사를 설치할 수 있습니다.

---

**Full command list / complete command reference:** [RFC § 1.10](../saipen/RFC.md#110-command-surface) — the authoritative list of every `saipen` command.
