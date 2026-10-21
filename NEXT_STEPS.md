# NEXT STEPS

Claude Code에게: 체크 안 된 첫 단계부터 **한 단계씩** 진행하고, 끝나면 `[x]`로 바꾼 뒤 사용자에게 확인받기.

## Phase 0 — 준비 ✅
- [x] 주제 237개 분류 (`data/taxonomy.csv`, `data/taxonomy.json`)
- [x] CLAUDE.md, NEXT_STEPS.md 작성

## Phase 1 — 저장소 만들기
- [x] GitHub에 `ten-infosec/knowledge-daily` 저장소 생성 (Public)
- [x] 이 폴더를 연결하고 첫 커밋·push
- [x] `.gitignore` (`.env`, `__pycache__/`, `.venv/`)
- [x] 파이썬 가상환경(.venv) + `requirements.txt` (requests, feedparser)

## Phase 2 — 수집기 1개로 시작 (arXiv)
- [x] `collector/arxiv.py`: taxonomy의 영문 키워드로 최근 1일 논문 검색
- [x] ★ 관심 주제만 대상으로 테스트 실행
- [x] 결과를 `state/seen.json`에 저장해 중복 방지
- [x] 첫 결과를 `digests/YYYY-MM-DD.md`로 출력 (요약 없이 제목·링크만)

## Phase 3 — 수집처 늘리기
- [x] PubMed (BCI·의료·바이오 주제)
- [x] IACR ePrint (암호 주제)
- [x] 기관·언론 RSS 목록 만들기 (`data/feeds.csv`) + `collector/rss.py`
- [ ] KCI / ScienceON API 키 발급 → 국내 논문 수집

## Phase 4 — AI 요약·선별
- [ ] Claude API로 각 항목 3줄 한국어 요약 + 난이도 + 읽을 이유
- [ ] 같은 소식 묶기(중복 제거), 주제별 상위 1~2건 선택
- [ ] 다이제스트 분량 20~30분으로 맞추기
- [ ] API 키는 GitHub Secrets `ANTHROPIC_API_KEY`

## Phase 5 — 매일 자동 실행
- [ ] `.github/workflows/daily.yml`: 매일 06:00 KST(= 21:00 UTC 전날) 실행
- [ ] 결과 다이제스트를 자동 커밋
- [ ] 수동 실행 버튼(workflow_dispatch) + dry_run 옵션

## Phase 6 — 읽기 목록
- [ ] 읽음 체크 방법 정하기 (GitHub 이슈 체크박스 / 노션 / 웹 페이지 중)
- [ ] 안 읽은 항목 다음 날로 넘기기
- [ ] 분야별 읽은 양 주간 통계

## 메모
- 과기정통부·우주항공청·핵융합에너지연구원 공식 RSS 주소 미확인 → `data/feeds.csv`에 enabled=0으로 둠. 주소 찾으면 url 채우고 1로
- KSEF C2 분과 이름 미확인 (스크린샷 잘림) → `KSC-02` 확인 후 수정
- 관심(★) 주제 47개 → 15~20개로 줄일지 검토
