<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**AI 코딩 에이전트를 위한 작업 연속성 프로토콜.** 일반 마크다운 형태의 지속적인 프로젝트 메모리로, 이전 대화 기록이 없는 에이전트라도 `/saipen continue`를 실행하여 1분 이내에 작업을 재개할 수 있습니다. 사전 설명 불필요, 어떤 벤더/모델이든, 언제든 가능합니다.

**단 하나의 명령. 건망증 제로.**

**빠른 키:** `cc`는 활성 Goal Mode 실행을 계속하고, `sss`는 코드를 건드리지 않고 상태를 보여주며, `ss`는 체크포인트를 저장하고 멈춥니다. [전체 13 키 맵 보기](saipen/RFC.md#110-command-surface). 키릴 문자 쌍둥이도 작동합니다: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

**응답 언어.** 에이전트는 기본적으로 **에스토니아어**로 응답합니다 — 이것은 설정이지 기벽이 아니며, SAIPEN에서 에스토니아어인 것은 이것뿐입니다. 한 곳에서 변경합니다: [`saipen/STYLE.md`](saipen/STYLE.md) 맨 위의 `reply_language:` 줄. `et` 에스토니아어, `en` 영어, `ru` 러시아어, `auto`는 보낸 메시지의 언어로 선택합니다. 프로토콜, 코드, 커밋과 모든 문서는 어떤 값에서도 영어로 유지됩니다.

**v7.189.0** | [Spec](SPEC.md) | [Guide](GUIDE.md) | [RFC](saipen/RFC.md) | [Style](saipen/STYLE.md) | [UI](saipen/UI.md) | [Conformance](saipen/CONFORMANCE.md) | plain markdown | zero deps | MIT

```text
User  ->  /saipen continue
Agent ->  reads STATE ("What do I do right now?")
Agent ->  reads BOARD ("What task am I picking up?")
Agent ->  reads next_action (executes command)
Agent ->  Works.
```

### 프로젝트 상태 > 모델 메모리
메모리는 모델의 기억 속이 아니라 프로젝트 내에 존재합니다. `Project -> Memory -> LLM` 구조가 `Project -> SAIPEN State -> LLM`으로 전환됩니다.

### 핵심 프로토콜 로직 & 보장 사항
- **핵심 상태 머신**: `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **제로 프롬프트 자율성**: 미완료 할 일이 없나요? 자동으로 `HUNT` (버그 스캔) → `ADD` (기능 확장) → `HUNT` 루프로 전환됩니다. 질문을 일절 하지 않습니다.
- **명시적 트리거**: `/saipen clean` (저장소 정리), `/saipen translate` (격리된 `.saipen/saitranslate/` 공장), `/saipen markhunt` (건드리지 않고 기록만 남기는 무제한 감사), `/saipen prepare` (인계용 작업 패키징), `/saipen validate` (적합성 검사), `/saipen goal` (자율 파도형 목표 실행). 메타/제어: `/saipen status` (읽기 전용 보고서), `/saipen stop` (체크포인트 생성 및 중단). 전체 목록: RFC.md § 1.10.
- **엄격한 신뢰성**: 배치 입력 파싱 (정밀한 1대1 티켓 처리), 커밋되지 않은 트리 수용 (작업 내용 절대 임의 삭제 안 함), 마스킹 처리 (`sk-***`).

## SAIPEN 기반 프로젝트
- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — SAIPEN 메모리 프로토콜과 네이티브하게 통합된 고성능 프롬프트 관리 도구.

## 2개의 계층

| 계층 | 필수 여부 | 목적 |
|---|---|---|
| **Core (핵심)** | ✅ | 안전한 작업 연속성 유지 |
| **Maintenance (유지보수)** | Core 상위 | 별도 지시 없이 소프트웨어 지속 진화 |

**자동화된 소프트웨어 진화.** 열려 있는 할 일이 남지 않았을 때 `/saipen`을 입력하면: `HUNT` 단계에서 버그, 쓰이지 않는 코드, 실패하는 테스트를 감지합니다. 문제가 없나요? `ADD` 단계에서 다음에 필요한 명확한 기능을 구현하고 검증한 뒤 다시 감시(hunt)합니다. 제품이 성숙해지면 우아하게 정지합니다.

**GOAL 모드.** `/saipen goal <원하는 목표>`는 보드를 피벗하고 (기존 티켓은 하향 조정되며 절대 삭제되지 않음) 새로운 목표를 향해 자율적으로 진행합니다. 티켓 간에 "계속할까요?"라고 묻지 않으며 VERIFY/REVIEW를 절대 건너뛰지 않습니다. SHIP 단계는 기존 원격 저장소로 자동 푸시합니다 (새 저장소인 경우에만 1회 확인 요청). 목표 배포 완료가 정지 지점도 아닙니다 — 곧바로 자율 HUNT/ADD 유지보수로 들어가지 제품이 성숙해지거나 블록되거나 실행 제한(3 파도 / 20개 티켓, 이후 체크포인트 및 보고)에 도달할 때까지 계속됩니다.

## 빠른 시작

**1. 머신당 1회 설치** -- Claude Code, Gemini, OpenCode, Aider, Antigravity 등에 프로토콜 학습:
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. 프로젝트 시작** -- 프로젝트 폴더에서 에이전트를 열고 입력:
> `saipen set`

설치 없이 사용하고 싶으신가요? 임의의 에이전트에 한 줄을 붙여넣으세요:
> Read <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md and follow them.

위 목록에 없는 플랫폼(DeepSeek, Qwen, 단독 OpenAI 등)인가요?
플랫폼별 설명은 `extensions/adapters/` 폴더에 위치해 있습니다.

## 문서 및 명세 링크
- **[SPEC.md](SPEC.md)** -- 공식 아키텍처, 설계 목표, 리트머스 테스트.
- **[RFC.md](saipen/RFC.md)** -- 에이전트가 실행하는 규범적 명세.
- **[GUIDE.md](GUIDE.md)** -- 인간용 튜토리얼 및 쉬운 가이드:
  - 🇷🇺 [Русский](guides/GUIDE_RU.md) | 🇺🇸 [English](guides/GUIDE_EN.md) | 🇪🇪 [Eesti](guides/GUIDE_EE.md) | 🇯🇵 [日本語](guides/GUIDE_JA.md) | 👴 [Версия Деда](guides/GUIDE_DED.md)
  - 🇺🇦 [Українська](guides/GUIDE_UK.md) | 🇩🇪 [Deutsch](guides/GUIDE_DE.md) | 🇫🇷 [Français](guides/GUIDE_FR.md) | 🇪🇸 [Español](guides/GUIDE_ES.md) | 🇮🇹 [Italiano](guides/GUIDE_IT.md)
  - 🇵🇹 [Português](guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](guides/GUIDE_NL.md) | 🇵🇱 [Polski](guides/GUIDE_PL.md) | 🇸🇪 [Svenska](guides/GUIDE_SV.md) | 🇩🇰 [Dansk](guides/GUIDE_DA.md)
  - 🇫🇮 [Suomi](guides/GUIDE_FI.md) | 🇳🇴 [Norsk](guides/GUIDE_NO.md) | 🇨🇳 [中文](guides/GUIDE_ZH.md) | 🇰🇷 [한국어](guides/GUIDE_KO.md) | 🇹🇭 [ไทย](guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) | 🇸🇦 [العربية](guides/GUIDE_AR.md) | 🇮🇱 [עברית](guides/GUIDE_HE.md)
  - 🇹🇷 [Türkçe](guides/GUIDE_TR.md) | 🇮🇳 [हिन्दी](guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) | 🇨🇿 [Čeština](guides/GUIDE_CS.md) | 🇷🇴 [Română](guides/GUIDE_RO.md)
  - 🇭🇺 [Magyar](guides/GUIDE_HU.md) | 🇧🇬 [Български](guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)
- **[STYLE.md](saipen/STYLE.md)** -- 에이전트 커뮤니케이션 스타일 및 어조 정의.
- **[UI.md](saipen/UI.md)** -- 다크 골든 Win95 UI 디자인 가이드라인.
- **[CONFORMANCE.md](saipen/CONFORMANCE.md)** -- 동작 테스트 시나리오 및 검증기 규칙.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

## ## 스크린샷

<details>
<summary>클릭하여 펼치기</summary>

<img src="assets/screenshot-freebuff.png" alt="FreeBuff 에이전트 지침" width="600"/>

<img src="assets/screenshot-nomadcode1.png" alt="nomadcode에서 saipen set" width="600"/>

<img src="assets/screenshot-20260801-003853.png" alt="saipen 스크린샷 2026-08-01" width="600"/>

</details>

<!-- source-digest: README.md sha256:951d8044313a6456 -->
