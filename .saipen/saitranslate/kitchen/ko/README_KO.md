<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
</p>

<div align="center">
  <h3><a href="README.ee.md">🇪🇪 LOE SEDA EESTI KEELES / ESTONIAN 🇪🇪</a></h3>
  <a href="README.md">🇬🇧 English</a> &nbsp;|&nbsp;
  <a href="README.ded.md">👴 Дед-Версия (Russian)</a> &nbsp;|&nbsp;
  <a href="README.ja.md">🇯🇵 日本語 (Japanese)</a>
</div>

# SAIPEN

**AI 코딩 에이전트를 위한 연속 프로토콜.**프로젝트 메모리는 plain
프로젝트 내의 Markdown 파일에(`.saipen/`), 따라서 호환되는 모든 cold agent —
채팅 기록 없이, 세션 메모리 없이 — 실행할 수 있고`/saipen continue`, 읽고
지속된`next_action`, 사용자에게 다시 설명하지 않고 작업을 계속할 수 있습니다. 상태는 프로젝트에 속하며, 특정 모델 제공업체의 메모리에 속하지 않습니다.
한 명령어로 작업을 재개합니다. 평문 파일 상태. 기계 검증된 계약.

**리포지토리는 모든 push 시 자체를 검증합니다; 설치, 상태, 검사 및**


설치 해제는 모두 로컬 — 클라우드 서비스, 데몬, 데이터베이스 없음.

[![Validation](https://github.com/vacterro/saipen/actions/workflows/validate.yml/badge.svg)](https://github.com/vacterro/saipen/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/vacterro/saipen?sort=semver&label=release)](https://github.com/vacterro/saipen/releases)
[![License: MIT](https://img.shields.io/github/license/vacterro/saipen?color=blue)](LICENSE)

**v7.238.2** | [사양](SPEC.md) | [가이드](GUIDE.md) | [코어](saipen/CORE.md) | [유지보수](saipen/MAINTENANCE.md) | [스타일](saipen/STYLE.md) | [UI](saipen/UI.md) | [일관성](saipen/CONFORMANCE.md) |MIT

**빠른 키:** `cc`는 프로젝트 컨텍스트를 수렴까지 계속합니다 (설정된 실행 중인 목표가 있으면 재개합니다), `sss`는 코드를 건드리지 않고 상태를 보여주며, `ss`는 체크포인트를 저장하고 멈춥니다. [전체 19 키 맵 보기](saipen/RFC.md#110-command-surface). 키릴 문자 쌍둥이도 작동합니다: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`. `ff` → `focus`; `xx` → `cut`; `vv` → `build`; `zz` → `undo`.

```text
Project
  |
  +-- .saipen/STATE.md ------ what is happening right now (phase, ticket, mode, next_action)
  +-- .saipen/BOARD.md ------ what work exists (DOING / TODO / DONE / BLOCKED)
  +-- .saipen/LOG.md -------- why the project reached this state (event history)
  +-- .saipen/KNOWLEDGE/ ---- what durable facts must survive sessions
          |
          v
   /saipen continue
          |
          v
      cold agent
          |
          v
     next_action -> work -> checkpoint -> next ticket
```

## 지속되는 것

라이브 프로젝트 메모리는`.saipen/`— 읽고, diff를 적용할 수 있는 일반 파일이며
코드 옆에 커밋할 수 있습니다. 차가운 에이전트는 파일에서 다섯 가지 질문에 답합니다
혼자:

|파일 / 필드|답변|
|---|---|
| `STATE.md` |지금 일어나고 있는 일은 무엇인가요?(단계, 활성 티켓, 운영 모드, 차단물) |
| `BOARD.md` |어떤 작업이 존재하나요 / 어떤 것이 활성 상태인가요?(티켓 그래프: DOING, TODO, DONE, BLOCKED) |
| `LOG.md` |왜 프로젝트가 이 상태에 이르렀나요?(추가 전용 이벤트 그래프) |
| `KNOWLEDGE/` |세션을 견디어야 할 지속 가능한 프로젝트 사실은 무엇인가요?|
| `next_action` (in`STATE.md`) |다음 에이전트가 실행해야 할 정확한 동작은 무엇인가요?|

이것은 설계 제안이 아닌 체크포인트 계약입니다:`saipen stop`그리고 모든
티켓 전환은 고정된 순서로 파일을 작성하고, 결과는
검증자에 의해 확인됩니다. 호스팅된 데이터베이스에 아무것도 저장되지 않으며, 아무것도 손실되지 않습니다 when a
세션 종료.

## 빠른 시작

**1. 기계당 한 번 설치**— Claude Code, Codex, Gemini, OpenCode를 가르침,
Aider, Antigravity, 그리고 일반적인`~/.agents/skills`리더(FreeBuff 등.):

```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

<sub>What that touches, so nothing is a surprise: it appends a marked
`<!-- SAIPEN:BEGIN -->...<!-- SAIPEN:END -->`에이전트 지시에 블록 추가
이미 가지고 있는 파일들(`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`,
`~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`)— 각각을 백업하여`.bak`먼저 —
그리고 프로토콜을 해당 스킬 폴더로 복사합니다. 그 외에는 아무것도 없습니다
경로, 데몬 없음, 네트워크 호출 없음.</sub>

**2. 프로젝트 시작**— 폴더에서 에이전트를 열고 입력하세요:

> `saipen set`

**설치 필요 없음?**어떤 에이전트에도 한 줄 붙여넣기:

> 읽기&lt;clone&gt;/saipen/BOOT.md 먼저(콜드 스타트 커널), 그 후&lt;clone&gt;/saipen/INDEX.md +&lt;복제&gt;/saipen/STYLE.md을 확인하고 따르세요.

**마음이 바뀌셨나요?**하나의 명령어로 되돌릴 수 있습니다:

```bash
powershell -ExecutionPolicy Bypass -File .\bootstrap\uninstall.ps1  # Windows
bash bootstrap/uninstall.sh                                         # macOS / Linux
```

그 명령어는 정확히 표시된 블록만 제거하고(파일의 나머지 부분은 그대로 두며), 저장하고
a `.uninstalled.bak`복사본을 먼저 만들고, 스킬 폴더를 제거합니다.

## 왜 챗 히스토리만 사용하지 않나요?

SAIPEN은 특정한 실패를 대상으로 합니다: 세션 종료 후 아무것도 기억하지 못하는 AI 코딩 에이전트
다른 도구와 습관은 그 문제의 일부를 해결합니다:

|접근법|무엇에 유용한가|무엇을 담지 않는가|
|---|---|---|
|채팅 기록 / 모델 메모리|편리하고, 설정 필요 없음|세션 및 제공업체에 따라 다름; 프로젝트와 함께 저장되지 않으므로, 차가운 에이전트는 이를 보지 못함|
|정적`AGENTS.md`/ 지시 파일|지속 가능한 서면 규칙과 관습|자체적으로 실시간 작업 상태를 나타내지 않음`next_action`, 또는 복구 기록|
|이슈 / TODO 추적기|작업 및 백로그 관리|자체적으로 에이전트의 이어가기 semantics을 정의하지 않습니다 — 재개 시 cold agent가 읽고 실행해야 할 내용|
| **SAIPEN** |라이브 실행 상태, 작업 대기열, 이벤트 기록, 지속 가능한 지식, 그리고 기계 검증 가능한 이어가기 규칙 — 코드 옆에 있는 일반 파일에 포함|아무것도 아닙니다; 그 조합이 계약입니다|

차이는 특정한 하나의 파일이 아닙니다. 차이는 SAIPEN이 재개 단계를 수행한다는 점입니다
기계 검증 가능: cold agent의 첫 번째 동작은`/saipen continue`입니다
지속된`next_action`에 의해 결정되고, 검증자에 의해 확인되며, 메모리에서 재구성되지 않습니다
공학적 증거

## SAIPEN은 규범적인 일반 파일 프로토콜과 실행 가능한, 실패 중심적인 것을 쌍으로 제공합니다.


검사. 저장소는 프로토콜/상태 기계 설계, Python
도구, 스키마 기반 상태, 복구 추론, 회귀 테스트,
다중 에이전트 워크플로우 경계, 그리고 명세 규율.

- **설계된 계약.** [SPEC.md](SPEC.md)는 파일 기반의
연속 모델과 안정적인 디스크 계약을 정의합니다;[CORE.md](saipen/CORE.md)
그리고[MAINTENANCE.md](saipen/MAINTENANCE.md)는 현재 표준적인 행동을 가지고 있습니다.
- **머신 체크 상태.**stdlib-only canonical
  [검증기](tools/validate.py)라이브
  [STATE 스키마](extensions/schemas/state.schema.json)및 단계 전환, 티켓 의존성, 이벤트 그래프 링크, 문서 간
불변량, 기능, 복구 상태를 확인합니다.
실패 커버리지.
- **CONFORMANCE.md** [는](saipen/CONFORMANCE.md)요구사항을
시나리오 테스트 조건에 매핑합니다.[](tests/scenarios/); the
  [시나리오 실행자](tools/run_scenarios.py)구조적 통과/실패 사례를 실행합니다
손상된 복구 상태, 유효하지 않은 전환, 의존성 순환 및
읽기 전용 제한을 포함합니다.
- **회귀 제어.** [audit_checks.py](tools/audit_checks.py)변형합니다
알려진 양호한 복사본을 사용하여 검증자가 여전히 경고를 내릴 수 있음을 증명하고,
영구적으로 녹색으로 유지되는 검사가 증거로 간주되는 대신에.
- **실행 가능한 계층.** [saipen.py](tools/saipen.py)기록된 상태를 제공합니다
작업;[bootstrap/](bootstrap/)설치, 제거 및 내보내기를 유지합니다
도우미와 선택적[pre-commit 훅 설치자](tools/install_hook.py).
- **명시적인 트레이드오프입니다.**핵심 프로토콜 상태는 실행 시간 의존성이 없는 일반 파일입니다
유효성 검증 및 CLI 도구는 Python이 필요하지만, 오직
표준 라이브러리만 사용하고`pip`설치가 필요하지 않습니다.

## 아키텍처

3개의 계층, 엄격한 단방향 의존성:

```text
CORE            continuation / state / checkpoint / validation       required
  └─ MAINTENANCE   autonomous HUNT / ADD / CLEAN evolution           optional, on top of Core
       └─ GOAL MODE / SUBAGENTS   opt-in throughput/execution        optional
```

코어는 유지보수에 의존하지 않음: 자율 진화가 비활성화된 상태에서, SAIPEN
는 여전히 완전한 연속 프로토콜이 되며 — 차가운 에이전트는 여전히 복구할 수 있다.

- **코어 상태 기계** — `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`.
- **자율 유지보수**— 보드 정지(에서 실행 가능한 것이 없음`## TODO`,
에서 아무것도 없음`## DOING`)그리고도`BLOCKED`? 자동 전이`HUNT` (버그 스캔)
  → `ADD` (기능 진화) → `HUNT`, 질문 없음. 세션은
  `BLOCKED`자동 사냥을 하지 않음
  ([유지보수 § 2.1](saipen/MAINTENANCE.md#21-autonomous-transitions)).
- **목표 모드** — `/saipen goal <objective>`보드를 회전시키고
목표를 VERIFY/REVIEW를 통해 전진시키며 자율 유지보수에 진입
완료 규칙이 실행되거나 실행 횟수가 한도에 도달할 때까지(3파동 / 20티켓,
그런 다음 체크포인트를 설정하고 보고) ([유지보수 § 2.4](saipen/MAINTENANCE.md#24-goal-mode-autonomous-execution)).
- **강화**— 배치 입력은 수술적 하나씩 티켓으로 파싱됨
  (CORE § 1.8); 더티 트리 연속은 미커밋 작업을 보존합니다(CORE § 1.5);
비밀과 유사한 값은 로그에서 삭제됩니다(`sk-***`) (CORE § 1.2).

## 일상적인 명령

일상적인 진입점; 현재 전체 표면은 여기에 존재합니다
[Core § 1.10](saipen/CORE.md#110-command-surface).

|명령|수행|
|---|---|
| `/saipen set` |프로젝트 채택: 생성`.saipen/`상태|
| `/saipen continue` |기존 프로젝트 상태에서 복구 — 재브리핑 없이|
| `/saipen plan` |요청 또는 원시 백로그를 티켓으로 전환|
| `/saipen goal <text>` |새로운 목표에 대한 자율적인 웨이브 실행|
| `/saipen validate` |준수 검사를 실행|
| `/saipen status` |읽기 전용 보고서: 단계, 티켓, 차단 사항, 오래된 상태|
| `/saipen stop` |체크포인트 설정 및 일시 중지|

<details>
<summary><b>More commands</b></summary>

|명령|실행|
|---|---|
| `/saipen hunt` |결함/개선 사항 스윕을 즉시 실행|
| `/saipen markhunt` |건조하고 제한 없는 감사 — 결과만 기록, 수정 없음|
| `/saipen ship` |릴리스 게이트; 허용 시 커밋, 태그, 푸시|
| `/saipen clean` |보드 및 상태 정리|
| `/saipen translate` |분리된 번역 공장|
| `/saipen prepare` / `/saipen collect` |인계/통합을 위한 패키지 작업|
| `/saipen test` |선언된 테스트 스위트 실행, 오직 보고만|
| `/saipen crew` |고정 순서의 크루 회로(hunt → reproduce → intake → build → translate → document → ship) |
| `/saipen improve` |프로토콜 개선에 대한 메타-제어 감사|
| `/saipen sub ...` |읽기 전용 하위 에이전트 생성/채택|

**패키지 키.** `ee`/`qq`완전한 번역/위키 패키지 준비 없이
통합;`eee`/`qqq`완료된 패키지만 수락한 후 통합, 검증,
검토 및 푸시.

**saicrew.** `sc` / `saipen crew` (`extensions/subs/crew.md`)전체를 걷는
고정된 순서로 내장된 크루 — 센서(saihunt, saitest, saipython, saiui),
생산자(saitranslate, saiwiki)그리고 Core가 유일한 메인 트리 작성자 —
다른 신선한 패스가 실제로 변경할 것이 아무것도 남지 않을 때까지. 그것은 정확히 하나를 추가합니다
자신만의 메커니즘: 내구성 있는 오케스트레이션 대상(`execution_intent:
수렴` with `수렴_대상: 크루`)회로가 재개 가능한 방식으로 만들어지고
증거로부터 추적 가능한 충돌을 일으키는 방식입니다.`saipen crew --dry-run --json`는
회로를 읽기 전용으로 만듭니다;`bootstrap/saipen_crew.*`은 선택적 수동
다중 창 도우미이며, 결코`saipen crew`를 의미하지 않습니다. 참조하십시오
[extensions/subs/crew.md](extensions/subs/crew.md).
</details>

## SAIPEN이 아닌 것들

- **LLM이나 모델**— 이는 에이전트가 따르는 프로토콜이며, 지능이 아닙니다.
- **IDE나 호스팅된 메모리 데이터베이스**— 상태는 프로젝트 내의 일반 파일입니다;
아무것도 호스팅되지 않습니다.
- **Git의 대체물**— Git은 여전히 버전 역사에 소유권을 가지고 있습니다; 커밋하십시오
  `.saipen/`다른 코드와 마찬가지로.
- **분산 합의**— 아래의 동시성 경계를 참조하십시오.
- **LLM이 올바른 엔지니어링 결정을 내릴 것이라는 보장**— 그것
맥락 손실과 행동 편차를 줄이지만, 확률적 에이전트를 불가능하게 만들지는 않습니다.
SAIPEN의 역할은 이어서/상태 계약에 더해 검증 및 도구입니다 —


다음 에이전트에게 기계 검증된 시작점을 제공하는 것이 마법보다 낫다.

**병행 경계.**일기화된 상태 변경(SAIOPS)사용
프로젝트 범위 OS 락과 복구 일기([OPS § 5](saipen/OPS.md#5-locks)).
일반적인 프로젝트 편집 및 연결되지 않은 작성자는 해당 락 외부에 있다. SAIPEN
분산 합의가 아니기 때문에 연결되지 않은 작성자는 외부에서
조정이 필요하다([SPEC](SPEC.md#concurrency--distribution-boundaries)).

## 생태계

|프로젝트|SAIPEN과의 관계|
|---|---|
| [SAIPENVIEW](https://github.com/vacterro/saipenview) |로컬 Windows 제어 센터 — SAIPEN 프로젝트 자동 감지`.saipen/`작업 공간을 시각화하고 실시간 상태 및 일치 여부를 표시하며 티켓을 관리하고 AI CLI를 실행합니다. 보조 도구이며, 권위는 아닙니다.|
| [SAIWORK](https://github.com/vacterro/saiwork) |SAIPEN을 통합한 Downstream CodeNomad 포크 — OpenCode 실행에`BOOT.md`/`STYLE.md`주입하고 SAIPEN 단축키 및 프로젝트 상태 보기 노출, 지속 가능한 프롬프트 대기열 추가.|
| [FastPrompter](https://github.com/vacterro/fastprompter) |자동 감지하는 포터블 Windows 임시 메모장 및 스니펫 관리자 —`.saipen/`폴더를 추가하고 읽기 전용 STATE/BOARD/LOG 뷰어를 제공합니다.|

## 문서

|문서|무엇인가|
|---|---|
| [SPEC.md](SPEC.md) |공식 아키텍처, 설계 목표, 리투스 테스트|
| [CORE.md](saipen/CORE.md) |규범적 연속성, 상태 기계, 명령 계약|
| [MAINTENANCE.md](saipen/MAINTENANCE.md) |자율 유지보수 및 목표 모드|
| [CONFORMANCE.md](saipen/CONFORMANCE.md) |실행 가능/행동 요구사항 및 검증기 규칙|
| [GUIDE.md](GUIDE.md) |인간용 튜토리얼|
| [RFC.md](saipen/RFC.md) |호환성 리디렉션을 분할된 규격 문서로|
| [STYLE.md](saipen/STYLE.md) |에이전트 커뮤니케이션 스타일 및 목소리|
| [UI.md](saipen/UI.md) |빈티지 골든 UI 디자인 가이드라인|
|브로셔|프레젠테이션 브로셔 —[EN](BROCHURE_EN.md) / [RU](BROCHURE_RU.md) / [ET](BROCHURE_ET.md) / [DED](BROCHURE_DED.md) / [JA](BROCHURE_JA.md) |

<details>
<summary><b>All 33 translated guides</b></summary>

🇷🇺 [Русский](guides/GUIDE_RU.md) · 🇺🇸 [영어](guides/GUIDE_EN.md) · 🇪🇪 [에스토니아어](guides/GUIDE_EE.md) · 🇯🇵 [日本語](guides/GUIDE_JA.md) · 👴 [Версия Деда](guides/GUIDE_DED.md)

🇺🇦 [Українська](guides/GUIDE_UK.md) · 🇩🇪 [독일어](guides/GUIDE_DE.md) · 🇫🇷 [프랑스어](guides/GUIDE_FR.md) · 🇪🇸 [스페인어](guides/GUIDE_ES.md) · 🇮🇹 [이탈리아어](guides/GUIDE_IT.md)

🇵🇹 [포르투갈어](guides/GUIDE_PT.md) · 🇳🇱 [네덜란드어](guides/GUIDE_NL.md) · 🇵🇱 [폴란드어](guides/GUIDE_PL.md) · 🇸🇪 [스웨덴어](guides/GUIDE_SV.md) · 🇩🇰 [덴마크어](guides/GUIDE_DA.md)

🇫🇮 [핀란드어](guides/GUIDE_FI.md) · 🇳🇴 [노르웨이어](guides/GUIDE_NO.md) · 🇨🇳 [中文](guides/GUIDE_ZH.md) · 🇰🇷 [한국어](guides/GUIDE_KO.md) · 🇹🇭 [ไทย](guides/GUIDE_TH.md)

🇻🇳 [베트남어](guides/GUIDE_VI.md) · 🇸🇦 [العربية](guides/GUIDE_AR.md) · 🇮🇱 [עברית](guides/GUIDE_HE.md) · 🇹🇷 [터키어](guides/GUIDE_TR.md) · 🇮🇳 [हिन्दी](guides/GUIDE_HI.md)

🇮🇩 [인도네시아어](guides/GUIDE_ID.md) · 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) · 🇨🇿 [체코어](guides/GUIDE_CS.md) · 🇷🇴 [루마니아어](guides/GUIDE_RO.md) · 🇭🇺 [ハンガリー語](guides/GUIDE_HU.md)

🇧🇬 [Български](guides/GUIDE_BG.md) · 🇸🇰 [슬로바키아어](guides/GUIDE_SK.md) · 🇭🇷 [크로아티아어](guides/GUIDE_HR.md)

</details>

## 설정 참고 사항

**답변 언어.**에이전트는 기본적으로**에스토니아어**로 답변합니다 — 이는
설정이며, 프로토콜의 요구사항이 아니며, SAIPEN에 대한 다른 내용도 에스토니아어가 아닙니다.
프로토콜, 코드, 커밋, 모든 문서는 모든
값에서 영어로 유지됩니다. 변경할 수 있는 곳은 하나뿐입니다:`reply_language:`파일의 맨 위에 있는
[`saipen/STYLE.md`](saipen/STYLE.md). `et`줄입니다.`en`에스토니아어,`ru`영어,
`auto`러시아어,

**는 당신이 보낸 메시지에서 선택합니다. Adapters.**인젝터가 지원하지 않는 플랫폼(DeepSeek, Qwen, standalone
OpenAI 등)? 플랫폼별 참고 사항은`extensions/adapters/`.

## 스크린샷

<details>
<summary><b>Click to expand</b></summary>

<img src="assets/screenshot-freebuff.png" alt="FreeBuff agent instructions" width="600"/>

<img src="assets/screenshot-nomadcode1.png" alt="saipen set in nomadcode" width="600"/>

<img src="assets/screenshot-20260801-003853.png" alt="saipen screenshot 2026-08-01" width="600"/>

</details>

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

<!-- translation-model: qwen3:14b contract:structured-markdown-v2 -->
<!-- source-digest: README.md sha256:bb47f7158db4a7a4fd99298427c1e4bc6859433c36435640e129cc6dad2a63b7 -->
