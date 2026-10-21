"""IACR ePrint 수집기: 암호학 논문 저장소의 최신 논문 RSS에서 암호 주제와 맞는 논문을 고른다.

RSS 메타데이터(제목·저자·초록)는 CC0 라이선스로 공개되어 있다 (eprint.iacr.org/robots.txt).
초록은 주제를 고르고 AI 요약에 넘기는 데만 쓰고 저장하지 않는다.
"""

# ===== Imports =====
# argparse: 터미널 옵션(--days 등)을 읽는 표준 라이브러리
import argparse
# calendar.timegm: RSS의 날짜(UTC 시간 구조체)를 숫자 시각으로 바꿈
import calendar
# datetime: "지금부터 N일 전"을 계산 / timezone.utc: 세계 표준시
from datetime import datetime, timedelta, timezone

# feedparser: RSS(XML)를 파이썬 데이터로 바꿔 줌
import feedparser
# requests: RSS 파일을 받아 옴
import requests

# common.py의 공통 설정·함수: 이름표, 주제 읽기, 키워드로 주제 고르기
from collector.common import USER_AGENT, best_topic, clean_text, load_topics

# ===== Settings =====
# 최신 논문 100건이 들어 있는 IACR ePrint RSS 주소
FEED_URL = "https://eprint.iacr.org/rss/rss.xml"


# ===== Collect =====
def collect(days=1, star_only=True):
    """RSS를 한 번 받아, 최근 days일 안에 올라온 논문 중 주제와 맞는 것만 돌려준다."""
    topics = load_topics("IACR", star_only)
    if not topics:
        return []
    try:
        # RSS 파일은 한 번만 받으면 됨 (주제마다 요청하지 않음)
        response = requests.get(FEED_URL, headers={"User-Agent": USER_AGENT}, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"[warn] IACR ePrint RSS 요청 실패: {e}")
        return []
    feed = feedparser.parse(response.text)

    # 이 시각보다 먼저 올라온 논문은 건너뜀
    since = datetime.now(timezone.utc) - timedelta(days=days)
    papers = []
    for entry in feed.entries:
        # published_parsed: feedparser가 날짜를 UTC 시간 구조체로 바꿔 둔 값
        published = datetime.fromtimestamp(calendar.timegm(entry.published_parsed), timezone.utc)
        if published < since:
            continue
        # 제목 + 초록으로 어떤 주제인지 판단 (초록은 여기서만 쓰고 버림)
        topic = best_topic(topics, f"{entry.title} {entry.get('summary', '')}")
        if topic is None:
            continue
        papers.append({
            "source": "iacr",
            # 링크 예: https://eprint.iacr.org/2026/880 → id "2026/880"
            "id": entry.link.split("eprint.iacr.org/")[-1],
            "topic_id": topic["id"],
            "title": " ".join(entry.title.split()),
            "authors": [a.name for a in entry.get("authors", [])],
            "link": entry.link,
            "published": published.date().isoformat(),
            # 초록: AI 요약에만 쓰고 저장하지 않음
            "abstract": clean_text(entry.get("summary", "")),
        })

    # 주제별 건수 출력 (다른 수집기와 같은 모양)
    for topic in topics:
        n = sum(1 for p in papers if p["topic_id"] == topic["id"])
        print(f"{topic['id']:7} {n:3}건  {topic['topic']} (IACR)")
    return papers
    # → 요청은 하루 1번, 키워드가 맞는 논문만 신문에 넣겠다


# ===== CLI =====
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IACR ePrint에서 최근 암호 논문 수집")
    parser.add_argument("--days", type=int, default=1, help="최근 며칠 (기본 1)")
    parser.add_argument("--all", action="store_true", help="관심(★) 주제가 아닌 것도 포함")
    args = parser.parse_args()

    papers = collect(days=args.days, star_only=not args.all)
    print(f"\n총 {len(papers)}건")
    for p in papers[:5]:
        print(f"- [{p['topic_id']}] {p['title']}\n  {p['link']}")
