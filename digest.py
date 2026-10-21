"""다이제스트(아침 신문) 만들기: 새 항목을 주제별로 묶어 digests/YYYY-MM-DD.md로 저장한다.

지금은 요약 없이 제목·저자·링크만 쓴다. (AI 요약은 Phase 4)
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


# ===== Render =====
def render(items, date_str):
    """새 항목 리스트를 Markdown 문자열로 만든다."""
    with open(TAXONOMY_PATH, encoding="utf-8") as f:
        # taxonomy 순서를 그대로 쓰기 위해 리스트로 읽음
        topics = json.load(f)

    # 주제 id별로 항목을 묶음. 예: {"QNT-05": [논문1, 논문2], ...}
    by_topic = {}
    for item in items:
        # setdefault: 키가 없으면 빈 리스트를 만들고, 그 리스트에 항목을 추가
        by_topic.setdefault(item["topic_id"], []).append(item)

    lines = [
        f"# 아침 지식 신문 — {date_str}",
        "",
        f"새 항목 {len(items)}건 · 주제 {len(by_topic)}개 · 출처: {source_summary(items)}",
        "",
    ]
    current_area = None
    # taxonomy 순서대로 돌면서, 오늘 항목이 있는 주제만 출력
    for topic in topics:
        papers = by_topic.get(topic["id"])
        if not papers:
            continue
        # 영역(예: 양자, 보안)이 바뀔 때마다 큰 제목을 새로 씀
        if topic["area"] != current_area:
            current_area = topic["area"]
            lines += [f"## {current_area}", ""]
        lines += [f"### {topic['topic']} `{topic['id']}` ({len(papers)}건)", ""]
        for p in papers:
            # 제목 속 대괄호가 Markdown 링크 문법을 깨뜨리지 않게 앞에 \를 붙임
            title = p["title"].replace("[", "\\[").replace("]", "\\]")
            # 출처 표시. 학술지 이름이 있으면 함께 (예: PubMed · Optics letters)
            where = SOURCE_LABELS.get(p["source"], p["source"])
            if p.get("venue"):
                where += f" · {p['venue']}"
            # 예: - [ ] [논문 제목](링크) — 저자 · arXiv · 2026-10-19
            lines.append(f"- [ ] [{title}]({p['link']}) — {format_authors(p['authors'])} · {where} · {p['published']}")
        lines.append("")

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
    day_items += [i for i in items if f"{i['source']}:{i['id']}" not in known]

    # ensure_ascii=False: 한글을 그대로 저장 / indent=1: 사람이 읽기 쉽게
    json_path.write_text(json.dumps(day_items, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    md_path = DIGEST_DIR / f"{date_str}.md"
    md_path.write_text(render(day_items, date_str), encoding="utf-8")
    return md_path
    # → 수동 실행 버튼으로 다시 돌려도, 아침 신문에 그날 찾은 항목이 모두 남게 하겠다
