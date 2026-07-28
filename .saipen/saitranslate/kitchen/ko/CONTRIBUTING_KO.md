# SAIPEN 기여하기 (Contributing to SAIPEN)

SAIPEN은 사양(specification)이 우선이고, 구현(implementation)은 그 다음입니다. 대부분의 기여는 애플리케이션 코드가 아니라 `saipen/RFC.md`, `phases/*.md` 파일, 또는 `tests/`의 적합성(conformance) 도구를 변경하는 것입니다.

## 변경을 제안하기 전에

여러분의 아이디어에 대해 [SAIPEN 리트머스 테스트](SPEC.md#the-saipen-litmus-test)를 실행해 보세요:
1. 에이전트 간의 전환을 더 안정적으로 만듭니까?
2. 서로 다른 모델들의 행동을 더 균일하게 만듭니까?
3. 컨텍스트 손실 확률을 줄입니까?

이 중 적어도 두 가지 질문에 대한 답이 "아니오"라면, 아무리 다른 곳에서 유용할지라도 이 프로토콜의 범위를 벗어나는 것입니다.

## 문제(Gap) 보고

다음을 설명하는 이슈를 열어주세요:
- 어느 파일/섹션에 문제가 있는지 (RFC.md, phase 문서, 스키마, 테스트 등)
- 구체적인 증거 (인용, 명령어와 출력, 현재 동작이 중단되는 시나리오)
- 대신 기대하는 사항

모호한 보고("뭔가 이상한 것 같아요")는 특정 `grep`이나 재현 방법보다 조치를 취하기가 훨씬 어렵습니다. 이것이 어떤 형태를 취해야 하는지는 버그 보고서 이슈 템플릿을 참고하세요.

## 변경하기

1. 편집하기 전에 `saipen/RFC.md` 및 관련 `phases/*.md` 파일 전체를 읽어보세요 — 표면적으로 보이는 문제(gap)의 대부분은 이미 다른 곳에서 다루어지고 있거나, 문서화된 이유로 인해 의도적으로 특정 범위로 제한되어 있습니다.
2. 이전 기록에 대해서는 `CHANGELOG.md`와 `.saipen/KNOWLEDGE/decisions.md`를 확인하세요. 이미 논의되어 거부된 결정을 아무 말 없이 다시 열지 마세요 — 만약 과거의 거절이 틀렸다는 새로운 증거가 있다면, PR 설명에 명시적으로 밝혀주세요.
3. 모든 규범적(normative) 변경(MUST/MUST NOT/SHOULD)에는 `CHANGELOG.md` 항목이 필요하며, 실용적인 경우 `tests/validate.sh` + `tests/validate.ps1` (두 플랫폼 모두)의 적용 범위(coverage)나 `tests/scenarios/` 아래의 픽스처(fixture)가 필요합니다.
4. PR을 열기 전에 정식(canonical) 검사기를 실행하세요:
   ```bash
   python tools/validate.py
   ```
   이것이 진짜 중요한 것입니다 -- `STATE.md`를 `extensions/schemas/state.schema.json`에 대해 검사하고, 밀봉된(sealed) 세그먼트를 넘나드는 `LOG.md` 이벤트 그래프를 탐색하며, 런타임 매니페스트와 인젝터 배선을 검증합니다. `tests/validate.sh` / `validate.ps1`은 Python이 없는 호스트를 위한 **동결된 이식 가능한 기본(frozen portable floor)**입니다 (각 파일 상단에 명시되어 있습니다): 검사 항목이 더 적으며, Python이 없는 호스트가 아무것도 없이 방치되지 않도록 유지됩니다. 변경 사항이 이 파일들에 영향을 준다면 함께 실행하세요. 그러나 절대 *대신* 실행하지 마세요 -- 기본(floor)만 통과한다고 해서 겉보기만큼 충분히 증명되지는 않습니다. CI는 모든 푸시와 PR에서 항상 정식 검사기를 실행합니다 (`.github/workflows/validate.yml`).
5. `phases/ship.md`의 규칙에 따라 `VERSION`을 올리세요 (문서 명확화는 patch, 새로운 규범적 동작은 minor, 호환성을 깨는 계약 변경은 major) 그리고 `README.md`의 버전 뱃지도 동기화하세요 — 이 저장소를 클론한 곳에서 `tests/validate.sh`/`.ps1`를 실행하면 이를 자동으로 확인합니다.

## 스타일 (Style)

- 프로토콜 및 phase 문서: 간결하게, RFC-2119 키워드를 필요한 곳에 사용하며 채우는 말(filler)이 없어야 합니다. `saipen/STYLE.md`를 참고하세요.
- 이 파일의 모든 내용, 커밋 메시지, 코드 주석, CHANGELOG는 명료하고 전문적(professional)이어야 합니다. 프로젝트 자체의 채팅/LOG 음성(`saipen/STYLE.md`)은 아티팩트에는 적용되지 않습니다.

## 범위를 벗어나는 것 (What's out of scope)

- SAIPEN을 분산 합의 시스템(distributed consensus 시스템)으로 전환하는 것. `SPEC.md`의 동시성 및 분산 경계(Concurrency & Distribution Boundaries) 섹션을 참고하세요.
- 기존 스켈레톤을 넘어선 기계 파싱 가능한 LOG 마커 문법. `LOG.md`는 고정된 형태를 둘러싼 산문으로 유지됩니다.
- `saipen doctor` 명령이나 `saipen validate` + `saipen status`와 중복되는 유사한 명령어.

이러한 내용들은 이전에 모두 제안되고 평가되었습니다. 이를 다시 열기 위해서는 새로운 증거가 필요하며 단순한 재질문은 안 됩니다.
