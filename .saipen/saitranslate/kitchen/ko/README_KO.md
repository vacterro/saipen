<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**AI 코딩 에이전트를 위한 작업 연속성 프로토콜.** 일반 마크다운 형태의 지속적인 프로젝트 메모리로, 이전 대화 기록이 없는 에이전트라도 `/saipen continue`를 실행하여 1분 이내에 작업을 재개할 수 있습니다. 사전 설명 불필요, 어떤 벤더/모델이든, 언제든 가능합니다.

**단 하나의 명령. 건망증 제로.**

**빠른 키:** `cc`는 프로젝트 컨텍스트를 수렴까지 계속합니다 (설정된 실행 중인 목표가 있으면 재개합니다), `sss`는 코드를 건드리지 않고 상태를 보여주며, `ss`는 체크포인트를 저장하고 멈춥니다. [전체 15 키 맵 보기](saipen/RFC.md#110-command-surface). 키릴 문자 쌍둥이도 작동합니다: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

**응답 언어.** 에이전트는 기본적으로 **에스토니아어**로 응답합니다 — 이것은 설정이지 기벽이 아니며, SAIPEN에서 에스토니아어인 것은 이것뿐입니다. 한 곳에서 변경합니다: [`saipen/STYLE.md`](saipen/STYLE.md) 맨 위의 `reply_language:` 줄. `et` 에스토니아어, `en` 영어, `ru` 러시아어, `auto`는 보낸 메시지의 언어로 선택합니다. 프로토콜, 코드, 커밋과 모든 문서는 어떤 값에서도 영어로 유지됩니다.

**v7.224.1** | [Spec](SPEC.md) | [Guide](GUIDE.md) | [RFC](saipen/RFC.md) | [Style](saipen/STYLE.md) | [UI](saipen/UI.md) | [Conformance](saipen/CONFORMANCE.md) | plain markdown | zero deps | MIT

```text

### 프로젝트 상태 > 모델 메모리

메모리는 모델의 기억 속이 아니라 프로젝트 내에 존재합니다. `Project -> Memory -> LLM` 구조가 `Project -> SAIPEN State -> LLM`으로 전환됩니다.


## Commands

The full surface is 16 commands; complete details in [RFC § 1.10](saipen/RFC.md#110-command-surface).

| Command | What it does |
|---|---|
| `/saipen set` | Adopt a project |
| `/saipen continue` | Resume exactly where you left off |
| `/saipen plan` | Turn a request or raw queue into tickets |
| `/saipen goal <text>` | Autonomous wave assault on a new objective |
| `/saipen hunt` | Force an immediate defect/improvement scan |
| `/saipen ship` | Version bump, changelog, tag, push |
| `/saipen clean` | Repository cleanup |
| `/saipen validate` | Conformance check |
| `/saipen markhunt` | Dry uncapped audit, record only |
| `/saipen translate` | Isolated translation factory |
| `/saipen prepare` | Package work for handoff |
| `/saipen collect` | Integrate a ready package |
| `/saipen status` | Read-only report |
| `/saipen stop` | Checkpoint and halt |

<sub>`saipen init` and `saipen sub` complete the sixteen; both are called by the protocol, not typed daily.</sub>

**Package keys.** `ee`/`qq` prepare a complete translation or wiki package without integrating; `eee`/`qqq` accept only a ready package, then integrate, verify, review, and push.

**Experimental: saicrew.** Optional bonus layer (`extensions/subs/`, zero Core changes) for running a multi-agent crew — one Core writer plus read-only `saihunt`/`saipython` workers reporting through their own `OUTBOX.md`. Under active live testing, not finalised — see `extensions/subs/crew.md`.

## Two layers

| Layer | Required | Purpose |
|---|---|---|
| **Core** | ✅ | Resume work safely |
| **Maintenance** | On top of Core | Evolve software without task direction |

**Automated evolution.** No open tasks remain, type `/saipen`: `HUNT` audits for bugs, dead code, and failing tests. Clean? `ADD` builds the next obvious missing capability, verifies it, and hunts again. Product mature -> stops gracefully.

**GOAL Mode.** `/saipen goal <what you want>` pivots the board (deprioritises old tickets, never deletes them) and drives the new objective forward — no "should I continue?" between tickets, VERIFY/REVIEW never skipped. SHIP auto-pushes to the existing remote; a brand-new repository still asks once. Shipping a goal is not the end point either — it transitions straight into autonomous HUNT/ADD maintenance until the product is mature, blocked, or the run hits its cap (3 waves / 20 tickets, then checkpoints and reports).

## Quick Start


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
> Read <clone>/saipen/INDEX.md + <clone>/saipen/STYLE.md and follow them.

위 목록에 없는 플랫폼(DeepSeek, Qwen, 단독 OpenAI 등)인가요?
플랫폼별 설명은 `extensions/adapters/` 폴더에 위치해 있습니다.


## Documentation

| Document | What it is |
|---|---|
| [SPEC.md](SPEC.md) | Formal architecture, design goals, litmus test |
| [RFC.md](saipen/RFC.md) | Normative specification agents execute |
| [GUIDE.md](GUIDE.md) | Human tutor and ELI5 guides |
| [STYLE.md](saipen/STYLE.md) | Agent communication style and voice definition |
| [UI.md](saipen/UI.md) | Vintage Golden UI design guidelines |
| [CONFORMANCE.md](saipen/CONFORMANCE.md) | Behavioural test scenarios and validator rules |

<details>
<summary><b>All 33 translated guides</b></summary>

🇷🇺 [Русский](guides/GUIDE_RU.md) · 🇺🇸 [English](guides/GUIDE_EN.md) · 🇪🇪 [Eesti](guides/GUIDE_EE.md) · 🇯🇵 [日本語](guides/GUIDE_JA.md) · 👴 [Версия Деда](guides/GUIDE_DED.md)

🇺🇦 [Українська](guides/GUIDE_UK.md) · 🇩🇪 [Deutsch](guides/GUIDE_DE.md) · 🇫🇷 [Français](guides/GUIDE_FR.md) · 🇪🇸 [Español](guides/GUIDE_ES.md) · 🇮🇹 [Italiano](guides/GUIDE_IT.md)

🇵🇹 [Português](guides/GUIDE_PT.md) · 🇳🇱 [Nederlands](guides/GUIDE_NL.md) · 🇵🇱 [Polski](guides/GUIDE_PL.md) · 🇸🇪 [Svenska](guides/GUIDE_SV.md) · 🇩🇰 [Dansk](guides/GUIDE_DA.md)

🇫🇮 [Suomi](guides/GUIDE_FI.md) · 🇳🇴 [Norsk](guides/GUIDE_NO.md) · 🇨🇳 [中文](guides/GUIDE_ZH.md) · 🇰🇷 [한국어](guides/GUIDE_KO.md) · 🇹🇭 [ไทย](guides/GUIDE_TH.md)

🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) · 🇸🇦 [العربية](guides/GUIDE_AR.md) · 🇮🇱 [עברית](guides/GUIDE_HE.md) · 🇹🇷 [Türkçe](guides/GUIDE_TR.md) · 🇮🇳 [हिन्दी](guides/GUIDE_HI.md)

🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) · 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) · 🇨🇿 [Čeština](guides/GUIDE_CS.md) · 🇷🇴 [Română](guides/GUIDE_RO.md) · 🇭🇺 [Magyar](guides/GUIDE_HU.md)

🇧🇬 [Български](guides/GUIDE_BG.md) · 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) · 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)

</details>

## Built with SAIPEN

- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — High-performance prompt management tool built natively around the SAIPEN memory protocol.

## Screenshots

<details>
<summary>Click to expand</summary>

<img src="assets/screenshot-freebuff.png" alt="FreeBuff agent instructions" width="600"/>

<img src="assets/screenshot-nomadcode1.png" alt="saipen set in nomadcode" width="600"/>

<img src="assets/screenshot-20260801-003853.png" alt="saipen screenshot 2026-08-01" width="600"/>

</details>

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

<!-- source-digest: README.md sha256:7550073ecb7103b2b34a8a8214fb35b3daddfc5bddb641691f1355e40cf8cc7f -->


