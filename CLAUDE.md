# knowledge-daily — 매일 아침 지식 신문

## 프로젝트 한 줄 요약
AI 에이전트가 237개 주제(미래기술 + 고교 교과 + KSEF 연구 분과)의 국내외 논문·기사·공지를 매일 모아,
주제별 핵심 1~2건을 한국어 3줄 요약한 "아침 신문"(다이제스트)으로 만들고, 읽은 기록을 남기는 시스템.

## 사용자
- 엄태은 (GitHub: ten-infosec). 헬스케어 AI 부트캠프 수강 중, 웹/앱·AI 개발자 지망.
- 파이썬은 아직 배우는 중 → 설명은 쉽게, 전문 용어는 처음 나올 때 풀어서.
- 답변은 한국어.

## 폴더 구조 (목표)
```
knowledge-daily/
├── CLAUDE.md            # 이 파일 (Claude Code가 먼저 읽음)
├── NEXT_STEPS.md        # 단계별 할 일 체크리스트
├── data/
│   ├── taxonomy.csv     # 주제 237개 (id, 계열, 영역, 주제, 영문 키워드, 태그, 수집처, 주기, 관심★)
│   └── taxonomy.json    # 같은 내용 JSON (코드에서 읽는 용도)
├── collector/           # 수집기 (소스별 모듈)
│   ├── arxiv.py
│   ├── pubmed.py
│   ├── rss.py
│   └── ...
├── summarizer/          # AI 요약·선별
├── digests/YYYY-MM-DD.md   # 날짜별 아침 신문
├── state/
│   ├── seen.json        # 이미 수집한 항목(중복 방지)
│   └── reading_log.json # 읽음 체크 기록
└── .github/workflows/daily.yml  # 매일 자동 실행 (GitHub Actions)
```

## 데이터 규칙
- `data/taxonomy.json`의 각 항목: `id`(예: QNT-01), `tier`, `area`, `topic`, `keywords`(영문 검색어), `tags`, `source`, `freq`(매일/주 1회/월 1회), `star`(관심 여부)
- 주기 적용: `star=true`는 매일. 나머지는 freq에 따라 순환 (주 1회 = id 순서로 요일 분배, 월 1회 = 날짜로 분배)
- 하루 다이제스트 목표: 20~30분 분량 (대략 주제 50개 이하, 주제당 1~2건)

## 수집처
- 해외 논문: arXiv API, PubMed E-utilities, IACR ePrint (RSS)
- 국내 논문: KCI, ScienceON (API 키 필요 — 발급 후 GitHub Secrets에 저장)
- 기사·공지: 언론사·기관 RSS (과기정통부, KASA, 한국핵융합에너지연구원 등)

## 꼭 지킬 규칙 (법·윤리)
1. **공식 API와 RSS만 사용.** HTML 무단 크롤링 금지. robots.txt와 이용약관 확인.
2. **원문 저장 금지.** 제목·저자·링크·날짜·직접 쓴 요약만 저장 (저작권).
3. **요청 간격 지키기.** arXiv는 요청 사이 3초 이상. 하루 1회 실행.
4. **API 키는 코드에 쓰지 않는다.** `.env`(로컬)와 GitHub Secrets만 사용, `.env`는 `.gitignore`에.

## 코드 스타일 (사용자 선호)
- 각 코드 줄 위에 함수·옵션·변수가 무엇인지 설명 주석.
- 코드 블록 아래에 "→ ~하겠다" 형식의 해석 주석.
- 구역 구분 주석은 영어로 (예: `# ===== Fetch arXiv =====`).
- 명령어를 알려줄 때는 어디서 실행하는지 함께 (예: WSL Ubuntu 터미널, Windows PowerShell).
- 명령어는 이유와 각 옵션의 역할도 함께 설명.
- 한 번에 한 단계씩, 사용자가 확인한 뒤 다음 단계로.

## Git
- 커밋 메시지는 영어, 짧게 (예: `feat: add arXiv collector`).
- 기능 단위로 이슈 → 브랜치 → PR → merge 흐름 사용 (GitHub 활동 기록용).
- 이메일은 noreply 주소 사용 (이미 global 설정됨).

## 참고: 비슷한 기존 프로젝트
- `kpqc-monitor` — KpqC 자료를 GitHub Actions로 매일 수집해 Markdown + JSON으로 커밋. 구조 참고 가능.
