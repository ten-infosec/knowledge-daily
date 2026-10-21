"""다이제스트(아침 신문) 만들기: 새 항목을 주제별로 묶어 digests/YYYY-MM-DD.md로 저장한다.

AI 요약(summarizer/claude.py)이 붙은 글은 요약과 함께, 아니면 제목·저자·링크만 쓴다.
"""

# ===== Imports =====
# json: taxonomy.json 읽기, 하루치 항목(digests/YYYY-MM-DD.json) 읽고 쓰기
import json
# datetime, timedelta, timezone: 한국 시간(KST = UTC+9) 기준 날짜를 구하기 위해 사용
from datetime import datetime, timedelta, timezone
# Path: 파일 경로를 다루는 도구
from pathlib import Path

# ===== Settings =====
# 프로젝트 최상위 폴더
ROOT = Path(__file__).resolve().parent
# 다이제스트를 저장할 폴더
DIGEST_DIR = ROOT / "digests"
# 주제 목록 파일
TAXONOMY_PATH = ROOT / "data" / "taxonomy.json"
# 한국 시간대 (UTC보다 9시간 빠름). GitHub Actions 서버는 UTC라서 직접 지정해 둠
KST = timezone(timedelta(hours=9))
# 출처 이름을 신문에 보여 줄 때 쓰는 표시 이름
SOURCE_LABELS = {"arxiv": "arXiv", "pubmed": "PubMed", "iacr": "IACR ePrint", "rss": "뉴스"}
# 저자가 이보다 많으면 앞의 몇 명만 쓰고 "외 N명"으로 줄임
MAX_AUTHORS = 3
# AI가 고른 글 하나를 읽는 데 걸리는 예상 시간(분): 요약을 읽고 원문을 훑어보는 정도
READ_MINUTES = {"입문": 1.0, "중급": 1.5, "심화": 2.0}
# 하루 신문 본문의 최대 예상 읽기 시간(분). 목표는 20~30분
MAX_READ_MINUTES = 30


# ===== Helpers =====
def today_kst():
    """한국 시간 기준 오늘 날짜 문자열 (예: 2026-10-21)."""
    return datetime.now(KST).date().isoformat()


def format_authors(authors):
    """저자 리스트를 "A, B, C 외 5명" 형태의 한 줄로 만든다."""
    if len(authors) <= MAX_AUTHORS:
        return ", ".join(authors)
    return ", ".join(authors[:MAX_AUTHORS]) + f" 외 {len(authors) - MAX_AUTHORS}명"


def source_summary(items):
    """출처별 건수를 "arXiv 84 · PubMed 50" 형태로 만든다."""
    counts = {}
    for item in items:
        counts[item["source"]] = counts.get(item["source"], 0) + 1
    # 표시 이름이 없으면 원래 이름을 그대로 씀
    return " · ".join(f"{SOURCE_LABELS.get(s, s)} {n}" for s, n in counts.items()) or "없음"


# ===== Reading time =====
def fit_reading_time(picks):
    """중요도 높은 글부터 MAX_READ_MINUTES분까지만 본문에 넣는다. (본문에 넣을 글, 넘친 글, 본문 예상 분)을 돌려준다."""
    # 정렬 기준: 중요도 높은 순 → 같으면 쉬운 글(읽는 시간 짧은 글) 먼저
    ranked = sorted(picks, key=lambda p: (-p["pick"]["importance"], READ_MINUTES[p["pick"]["difficulty"]]))
    kept, overflow, minutes = [], [], 0.0
    for p in ranked:
        cost = READ_MINUTES[p["pick"]["difficulty"]]
        # 이 글을 넣어도 시간 안이면 본문으로, 넘으면 "시간 여유가 있으면"으로
        if minutes + cost <= MAX_READ_MINUTES:
            kept.append(p)
            minutes += cost
        else:
            overflow.append(p)
    return kept, overflow, minutes
    # → 고른 글이 아무리 많아도 아침 신문 본문은 30분 안에 읽히게 하겠다


# ===== Render =====
def item_line(p):
    """항목 하나를 "- [ ] [제목](링크) — 저자 · 출처 · 날짜" 한 줄로 만든다."""
    # 제목 속 대괄호가 Markdown 링크 문법을 깨뜨리지 않게 앞에 \\를 붙임
    title = p["title"].replace("[", "\\[").replace("]", "\\]")
    # 출처 표시. 학술지·매체 이름이 있으면 함께 (예: PubMed · Optics letters)
    where = SOURCE_LABELS.get(p["source"], p["source"])
    if p.get("venue"):
        where += f" · {p['venue']}"
    # 저자가 없으면(뉴스 기사 등) 저자 칸을 빼고 씀
    meta = " · ".join(x for x in (format_authors(p["authors"]), where, p["published"]) if x)
    return f"- [ ] [{title}]({p['link']}) — {meta}"


def pick_lines(p):
    """AI가 고른 항목: 한 줄 + 난이도·중요도 + 3줄 요약 + 읽을 이유 + 같은 소식 링크."""
    pick = p["pick"]
    # 중요도 3 → ★★★☆☆
    stars = "★" * pick["importance"] + "☆" * (5 - pick["importance"])
    lines = [f"{item_line(p)} · **{pick['difficulty']}** · {stars}"]
    # 목록 안에 들여쓴 인용(>)으로 요약을 넣어, 체크박스 항목에 붙어 보이게 함
    lines += [f"  > {i}. {sentence}" for i, sentence in enumerate(pick["summary"], 1)]
    lines.append(f"  >\n  > **읽을 이유:** {pick['why']}")
    if pick["related"]:
        links = ", ".join(f"[{r['venue']}]({r['link']})" for r in pick["related"])
        lines.append(f"  >\n  > 같은 소식: {links}")
    return lines


def render(items, date_str):
    """하루치 항목 리스트를 Markdown 문자열로 만든다.

    AI가 고른 글은 요약과 함께 주제별로(30분 분량까지), 넘친 글과 고르지 않은 글은 맨 아래 접힌 목록으로 보여 준다.
    요약을 거치지 않은 글(API 키 없음·요약 실패)은 예전처럼 주제별 목록에 그대로 나온다.
    """
    with open(TAXONOMY_PATH, encoding="utf-8") as f:
        # taxonomy 순서를 그대로 쓰기 위해 리스트로 읽음
        topics = json.load(f)

    # 같은 소식으로 묶인 글은 고른 글 밑에 "같은 소식"으로만 나오므로 목록에서 뺌
    shown = [i for i in items if "dup_of" not in i]
    # AI가 고른 글을 읽기 시간 안에 드는 것(kept)과 넘친 것(overflow)으로 나눔
    kept, overflow, minutes = fit_reading_time([i for i in shown if "pick" in i])
    # 본문에 나올 글: 시간 안에 드는 고른 글 + 요약을 거치지 않은 글
    main = kept + [i for i in shown if not i.get("summarized")]
    # 접힌 목록에 나올 글: 요약을 거쳤지만 고르지 않은 글
    rest = [i for i in shown if i.get("summarized") and "pick" not in i]
    # 각 글이 어느 칸에 들어갔는지 기록 → 하루치 JSON에 저장되어 웹 페이지가 같은 구성으로 보여 줌
    for group, name in ((main, "main"), (overflow, "overflow"), (rest, "rest")):
        for i in group:
            i["section"] = name
    for i in items:
        if "dup_of" in i:
            i["section"] = "dup"

    # 주제 id별로 본문 글을 묶음. 예: {"QNT-05": [논문1, 논문2], ...}
    by_topic = {}
    for item in main:
        # setdefault: 키가 없으면 빈 리스트를 만들고, 그 리스트에 항목을 추가
        by_topic.setdefault(item["topic_id"], []).append(item)

    summary_line = f"새 항목 {len(items)}건 · 주제 {len(by_topic)}개 · 출처: {source_summary(items)}"
    if kept:
        # 예상 읽기 시간은 반올림해서 정수 분으로 (round: 반올림)
        summary_line = (f"오늘의 글 {len(kept)}건 · 예상 읽기 시간 약 {round(minutes)}분 "
                        f"(수집 {len(items)}건 중 AI 선택) · 출처: {source_summary(items)}")
    lines = [f"# 아침 지식 신문 — {date_str}", "", summary_line, ""]

    current_area = None
    # taxonomy 순서대로 돌면서, 본문에 나올 글이 있는 주제만 출력
    for topic in topics:
        papers = by_topic.get(topic["id"])
        if not papers:
            continue
        # 영역(예: 양자, 보안)이 바뀔 때마다 큰 제목을 새로 씀
        if topic["area"] != current_area:
            current_area = topic["area"]
            lines += [f"## {current_area}", ""]
        lines += [f"### {topic['topic']} `{topic['id']}` ({len(papers)}건)", ""]
        # 고른 글을 중요도 높은 순으로 먼저, 그다음 요약 안 된 글
        # sorted(key=...): 정렬 기준. 고른 글은 -중요도, 나머지는 0이라 뒤로 감
        for p in sorted(papers, key=lambda x: -x["pick"]["importance"] if "pick" in x else 0):
            lines += pick_lines(p) if "pick" in p else [item_line(p)]
        lines.append("")

    if overflow:
        # 요약은 있지만 30분을 넘쳐 본문에서 뺀 글. 주제 이름을 앞에 붙여 접힌 목록으로
        topic_names = {t["id"]: t["topic"] for t in topics}
        lines += ["<details>", f"<summary>시간 여유가 있으면 — 요약 {len(overflow)}건 더 보기</summary>", ""]
        for p in overflow:
            lines += [f"**{topic_names.get(p['topic_id'], p['topic_id'])}**", ""] + pick_lines(p) + [""]
        lines += ["</details>", ""]

    if rest:
        # <details>: GitHub에서 클릭하면 펼쳐지는 접힌 목록
        lines += ["<details>", f"<summary>그 밖의 수집 항목 {len(rest)}건 (AI가 고르지 않음)</summary>", ""]
        lines += [item_line(p) for p in rest]
        lines += ["", "</details>", ""]

    if not items:
        lines += ["오늘은 새 항목이 없습니다.", ""]
    return "\n".join(lines)
    # → 항목마다 [ ] 체크박스를 붙여, 나중에 Phase 6 읽음 체크에 쓸 수 있게 하겠다


def write_digest(items):
    """오늘 항목을 digests/YYYY-MM-DD.json에 모으고, 그 전체로 .md를 만들어 저장한다. .md 경로를 돌려준다.

    같은 날 여러 번 실행해도 앞선 실행에서 찾은 항목이 사라지지 않는다.
    (앞선 항목은 이미 seen.json에 있어서 다시 수집되지 않기 때문에, 따로 모아 두어야 함)
    """
    date_str = today_kst()
    DIGEST_DIR.mkdir(exist_ok=True)
    json_path = DIGEST_DIR / f"{date_str}.json"

    # 오늘 앞서 저장한 항목이 있으면 불러옴
    day_items = []
    if json_path.exists():
        day_items = json.loads(json_path.read_text(encoding="utf-8"))
    # "출처:ID" 집합으로 이미 있는 항목을 확인하고, 새 항목만 뒤에 붙임
    known = {f"{i['source']}:{i['id']}" for i in day_items}
    # 초록(abstract)은 AI 요약에만 쓰고 저장하지 않음 (원문 저장 금지 규칙)
    # {k: v ... if k != "abstract"}: abstract 키만 뺀 새 딕셔너리
    day_items += [{k: v for k, v in i.items() if k != "abstract"}
                  for i in items if f"{i['source']}:{i['id']}" not in known]

    # render가 각 글에 section(어느 칸인지)을 붙이므로, Markdown을 먼저 만들고 JSON을 저장
    md_path = DIGEST_DIR / f"{date_str}.md"
    md_path.write_text(render(day_items, date_str), encoding="utf-8")
    # ensure_ascii=False: 한글을 그대로 저장 / indent=1: 사람이 읽기 쉽게
    json_path.write_text(json.dumps(day_items, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return md_path
    # → 수동 실행 버튼으로 다시 돌려도, 아침 신문에 그날 찾은 항목이 모두 남게 하겠다
