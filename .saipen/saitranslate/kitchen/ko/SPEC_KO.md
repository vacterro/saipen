# SAIPEN 사양 (Specification)

## 초록 (Abstract)
**설계 목표 #1: 채팅 내역이 전혀 없는 초기 상태(cold)의 에이전트라도 사용자가 컨텍스트를 반복할 필요 없이 `/saipen continue`를 실행하여 1분 이내에 생산적인 작업을 재개할 수 있어야 합니다.**

SAIPEN은 호환 가능한 모든 AI 에이전트가 재브리핑 없이 모든 프로젝트를 안전하게 이어서 작업할 수 있도록 보장합니다. 이는 엔지니어링 AI 에이전트를 위한 ABI(Application Binary Interface)로, 기억 상실 문제를 해결하는 호환성 계층입니다. 오늘 Claude를 사용하든, 내일 Gemini를 사용하든, 모레 GPT를 사용하든, 모든 에이전트는 사용자가 컨텍스트를 다시 서술할 필요 없이 동일한 프로젝트 상태에서 작동하게 됩니다.

### 핵심 철학: 프로젝트 상태 > 모델 메모리
메모리는 다른 모델의 머릿속이 아니라 코드 옆에 있어야 합니다. SAIPEN은 패러다임을 `Project -> Memory -> LLM`에서 `Project -> SAIPEN State -> LLM`으로 전환합니다. 메모리는 프로젝트에 속합니다.

기본적으로 SAIPEN은 LLM 에이전트를 위한 이식 가능한 파일 기반 연속성 프로토콜을 사용합니다. 구현은 다를 수 있습니다(MAY). 하지만 디스크 상의 규약은 반드시 안정적으로 유지되어야 합니다(MUST). 이 프로토콜의 모든 요소는 오직 '연속성 테스트(Continuation Test)'를 충족하기 위해 존재합니다.

SAIPEN은 창조적인 것이 아니라 진화적인 것입니다. 목적은 소프트웨어를 발명하는 것이 아니라 완성하는 것입니다. ADD는 기존 설계 패턴, 산업 관례 및 명백한 기능적 대칭성을 확장합니다.

- **`STATE`**: *"지금 당장 무엇을 해야 하나?"*에 답하기 위해 존재합니다.
- **`BOARD`**: *"어떤 작업을 수행 중인가?"*에 답하기 위해 존재합니다.
- **`LOG`**: *"어떻게 이 지점까지 오게 되었나?"*에 답하기 위해 존재합니다.
- **`KNOWLEDGE`**: *"이 프로젝트의 영구적인 진실은 무엇인가?"*에 답하기 위해 존재합니다.
- **`next_action`**: SAIPEN의 핵심입니다. *"작업을 재개하기 위해 지금 당장 실행해야 할 정확한 명령어는 무엇인가?"*에 답합니다.

## SAIPEN 리트머스 테스트

이 프로토콜에 제안되는 모든 변경 사항이나 새로운 아이디어는 반드시 다음 세 가지 질문을 통과해야 합니다(MUST):
1. 에이전트 간의 전환을 더 안정적으로 만듭니까?
2. 서로 다른 모델들의 행동을 더 균일하게 만듭니까?
3. 컨텍스트 손실 확률을 줄입니까?

이 중 적어도 두 가지 질문에 대한 답이 "아니오"라면 해당 아이디어는 거부됩니다. SAIPEN은 새로움보다 규율, 재현 가능성, 그리고 신뢰성을 우선시합니다.

## 아키텍처 (Architecture)

프로토콜은 엄격하게 규범적(normative)입니다. SAIPEN은 개념적으로 두 개의 계층으로 나뉩니다: **Core (핵심)**와 **Maintenance (유지보수)**.
- **Core 계층**은 벤더 중립적이고 안전한 작업 연속성을 보장합니다.
- **Maintenance 계층**은 Core 위에 구축된 자율적인 소프트웨어 진화 모델입니다.

두 계층 아래에서 SAIPEN은 절대 얽히지 않는 세 가지 관심사를 분리합니다:
**정확성과 연속성** (Core -- `STATE`/`BOARD`/`LOG`/`KNOWLEDGE`, 기능 협상, 체크포인팅), **무인 진화** (Maintenance -- `HUNT`/`ADD`/`CLEAN`, 기본 `saipen`/`saipen continue`에서 완전 작동), 그리고 **처리량** (Goal 모드, 하위 에이전트 -- 둘 다 명시적인 선택 사항, §1.3/§2.4). Goal 모드를 비활성화하더라도 프로토콜은 변경되지 않으며, 한 번에 하나의 티켓을 처리합니다. 하위 에이전트를 비활성화하더라도 `HUNT`는 6개 카테고리를 순차적으로 실행하여 동일한 결과를 냅니다. Maintenance 계층 없이 Core만 단독으로 사용해도, 규칙은 유지되며 초기화된(cold) 에이전트는 여전히 올바르게 작업을 재개합니다. 각 계층은 역방향 의존성 없이 아래 계층 위에 구축됩니다; 상위의 어떠한 것도 하위 기능이 존재해야만 동작하는 것은 아닙니다.

```text
saipen/
  RFC.md                    규범적 사양 (Core 및 Maintenance로 구분됨)
  CONFORMANCE.md             자체 검사 벡터 + 시나리오 커버리지 테이블
  SKILL.md                  기술 읽기 지원 플랫폼을 위한 얇은 진입점
  STYLE.md                  음성: chat, LOG.md, artifacts
  UI.md                     Vintage Golden UI 사양 (UI 작업 시 필수)
  BOOT.md                   ~콜드스타트 커널: 베어 `continue`가 필요로 하는
                             고속 경로, 위의 어떤 것도 로드되기 전
  phases/                   엄격한 상태 머신 로직 -- RFC § 1.6 열거 값당
                             16개 문서 (tools/validate.py에 의한 양방향
                             기계 검증 포함)
    [Core Phases]
    init.md / plan.md / scout.md / build.md / verify.md / review.md / ship.md / done.md / blocked.md
    [Maintenance Phases]
    hunt.md / markhunt.md / add.md / clean.md / translate.md

    [Infrastructure]
    prepare.md              다음 에이전트로 인계할 패키지 작업
    validate.md             적합성 테스트

extensions/                 <- 적응 계층 (THE ADAPTIVE LAYER)
  adapters/                 플랫폼별 명령 브리지 (인젝터가 자동 감지하지 못하는 플랫폼용, README.md가 여기를 가리킴)
  schemas/                  tools/validate.py가 기계 판독하는 state.schema.json (STATE 형태의 단일 진실 공급원); board/log 스키마는 참조용으로만 유지 (schemas/README.md 참고)
  templates/                초기 .saipen/ 보일러플레이트
  security/                 프로젝트에 복사하기 위한 예제 훅 (RFC § 1.9, VERIFY에 연결됨)
  performance/              프로젝트에 복사하기 위한 예제 훅 (RFC § 1.9, REVIEW에 연결됨)
  subs/                     예제 읽기 전용 연구 하위 에이전트 (RFC § 1.9) -- 하위 에이전트별 자체 STATE/BOARD/LOG, 결과는 OUTBOX를 통해서만 전달, 프로젝트로 두 번째 쓰기 경로를 절대 만들지 않음

bootstrap/                  <- 설치/내보내기/제거 (한 번에 한 머신)
  inject.ps1 / .sh          SAIPEN 블록 + 스킬 복사본 설치 (README 빠른 시작)
  uninstall.ps1 / .sh       inject의 반대 -- 블록 + 스킬 복사본 제거
  export.ps1 / .sh          백업을 위해 프로젝트의 .saipen/ 아카이브
  saipen_crew.bat / .sh     3창 크루 레이아웃 열기 (보너스, extensions/subs/crew.md)

tools/                      <- 표준 검사기 및 저장소 유틸리티
  validate.py               표준 적합성 검사기 (표준 Python, 설치 불필요; state.schema.json에 대해 STATE 직접 검증, 쉘 스크립트가 할 수 없는 그래프 검사 추가 수행)
  install_hook.py           validate.py를 실행하는 pre-commit 훅 설치
  uninstall_hook.py         해당 훅만 제거 (이전 훅 복원)

tests/                      <- 적합성 계층
  validate.ps1 / .sh        Python이 없는 호스트를 위한 동결된 이식 가능 기준선 -- 새로운 검사는 tools/validate.py에만 추가됨
  scenarios/                모의 상태들 (충돌 복구, 소유권 충돌 등)
```

## 양방향 기능 협상 (Two-Way Capability Negotiation)
에이전트는 자신이 할 수 있는 것을 단순히 선언하지 않습니다; 프로토콜이 필요한 것을 요구합니다.
프로젝트는 그 상태에 `requires: [filesystem, git, shell, python]`을 정의합니다. 에이전트는 요구 사항에 대해 호스트 기능을 교차 참조하고 모드를 잠급니다(`mode` 설정, 예: `full`, `read-only`).

## 그래프 기반 이벤트 로깅 (Graph-Based Event Logging)
SAIPEN의 로그는 선형 문자열이 아닙니다. 이벤트 ID(`E-001`)를 사용한 결정(decisions)의 비순환 그래프(acyclic graph)를 형성합니다. 이를 통해 복잡한 분기, 에이전트 병합 및 정밀한 감사 추적이 가능합니다.

## 아키텍처 결정 기록 (ADR)
일시적인 이벤트 로그에는 영구적인 지식이 저장되지 않습니다. SAIPEN은 구조적인 아키텍처 결정이 ADR로 지속될 것을 의무화합니다 (예: `KNOWLEDGE/ADR-001-use-sqlite.md`).

## 동시성 및 분산 경계 (Concurrency & Distribution Boundaries)
SAIPEN은 파일 기반 소유권(`owner`, `claim_time`)과 순차적 그래프(`LOG.md`)를 통해 상태 무결성을 보장합니다. 하지만 **SAIPEN은 상태 프로토콜이지 분산 합의 알고리즘이 아닙니다.**
- **로컬/공유 파일 시스템**: 충돌 해결은 원자적(atomic) 파일 시스템 쓰기("첫 번째 커밋 우선")에 의존합니다.
- **네트워크/분산 환경**: 에이전트들이 실시간 파일 동기화 없이 연결이 끊긴 머신 간에 동작하는 경우, `BOARD.md` 소유권에 경쟁 상태(race condition)가 발생합니다. 고도로 분산된 설정에서, SAIPEN 디스크 상 프로토콜 규약은 반드시 안정적으로 유지되어야 합니다 -- 프로젝트 상태 자체는 SAIPEN 고유 규칙(§ 1.5 체크포인팅)에 따라 지속적으로 변경되지만, 그 규칙이 따르는 프로토콜 형태는 절대 변하지 않습니다.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>
