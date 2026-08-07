<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# SAIPEN 가이드 (한국어)

[TRANSLATED KO]:
It is 2026 and the AI woke up. The assistants stopped being chat toys — they open your project, write the code, run the tests, and finish a job while you go make coffee. There is one thing they cannot do. They cannot remember. Close the window and everything they learned about your work is gone: what you were building, what you already tried, which idea died on Tuesday. Every morning you brief a brilliant stranger from scratch.

This is the fix for that one thing.

## 빠른 시작

## 명령어

## 알아두면 좋은 것
- 프로젝트로 돌아왔을 때 커밋되지 않은 변경사항이 있다면? 정상입니다 -- SAIPEN은 매 단계가 아니라 `ship` 시점에만 커밋합니다. 에이전트는 무언가를 건드리기 전에 먼저 그 변경사항이 누구의 것인지 확인합니다.
- 실제 아키텍처 결정을 기억하게 하고 싶다면? `.saipen/KNOWLEDGE/`에 `decisions.md` 파일 하나로, 또는 번호가 매겨진 `ADR-001.md` 파일들로 넣으세요.
- 이 머신에 git이나 shell이 없다면? 에이전트는 추측하는 대신 명확하게 말합니다 (`mode`, `WAIT: <category> -- <질문>`). (카테고리는 일곱 가지 중 하나입니다: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; 어떤 종류의 답변이 차단을 해제하는지 알려줍니다)
- 안전망을 원하세요? `python <saipen-클론>/tools/install_hook.py`로 커밋 전 검사를 설치할 수 있습니다.