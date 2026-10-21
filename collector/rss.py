"""RSS 수집기: data/feeds.csv에 적힌 기관·언론 RSS를 읽어, 주제와 맞는 기사만 고른다.

기사 본문은 저장하지 않고 제목·링크·날짜만 남긴다 (원문 저장 금지 규칙).
요약문(description)은 주제를 고르고 AI 요약에 넘기는 데만 쓰고 저장하지 않는다.
"""

# ===== Imports =====
# argparse: 터미널 옵션(--days 등)을 읽는 표준 라이브러리
import argparse
# calendar.timegm: RSS 날짜(UTC 시간 구조체)를 숫자 시각으로 바꿈
import calendar
# csv: feeds.csv를 한 줄씩 딕셔너리로 읽음
import csv
# time: 요청 사이에 쉬는 time.sleep()
import time
# datetime: "지금부터 N일 전" 계산 / timezone.utc: 세계 표준시
from datetime import datetime, timedelta, timezone
# Path: 파일 경로를 다루는 도구
from pathlib import Path

# feedparser: RSS/Atom(XML)을 파이썬 데이터로 바꿔 줌
import feedparser
# requests: RSS 파일을 받아 옴
import requests

# common.py의 공통 설정·함수: 이름표, 주제 읽기, 키워드로 주제 고르기
from collector.common import USER_AGENT, best_topic, clean_text, load_topics

# ===== Settings =====
# 피드 목록 파일
FEEDS_PATH = Path(__file__).resolve().parent.parent / "data" / "feeds.csv"
# 피드 사이 쉬는 시간(초). 서로 다른 사이트지만 예의상 1초
REQUEST_DELAY = 1


# ===== Load feeds =====
def load_feeds():
    """feeds.csv에서 enabled=1이고 주소가 있는 피드만 돌려준다."""
    # newline="": csv 모듈이 줄바꿈을 직접 처리하게 함 / utf-8-sig: 엑셀이 붙이는 BOM 문자도 처리
    with open(FEEDS_PATH, encoding="utf-8-sig", newline="") as f:
        # DictReader: 첫 줄(name,url,...)을 키로 써서 각 줄을 딕셔너리로 만듦
        return [row for row in csv.DictReader(f) if row["enabled"] == "1" and row["url"]]


# ===== Helpers =====
def entry_time(entry):
    """기사 날짜를 datetime으로. 날짜가 없거나 형식을 못 읽으면 None."""
    # published가 없으면 updated(수정 시각)를 씀
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return datetime.fromtimestamp(calendar.timegm(parsed), timezone.utc)


# ===== Collect =====
def collect(days=1, star_only=True):
    """피드를 하나씩 받아, 최근 days일 안의 기사 중 주제와 맞는 것만 공통 형식으로 돌려준다."""
    # "뉴스"가 수집처에 들어간 주제 + 피드별 topic_filter로 후보를 좁힘
    all_topics = load_topics("", star_only)
    since = datetime.now(timezone.utc) - timedelta(days=days)
    items = []
    for i, feed_info in enumerate(load_feeds()):
        if i > 0:
            time.sleep(REQUEST_DELAY)
        # 이 피드가 다룰 주제만 후보로 (예: "보안 뉴스" → 수집처에 "보안 뉴스"가 있는 주제)
        topics = [t for t in all_topics if feed_info["topic_filter"] in t["source"]]
        if not topics:
            continue
        try:
            response = requests.get(feed_info["url"], headers={"User-Agent": USER_AGENT}, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            # 피드 하나가 실패해도 나머지는 계속
            print(f"[warn] {feed_info['name']} 요청 실패: {e}")
            continue
        # response.content(바이트)를 넘기면 feedparser가 인코딩(한글 등)을 알아서 판단
        feed = feedparser.parse(response.content)

        found = 0
        for entry in feed.entries:
            published = entry_time(entry)
            # 날짜가 있는데 오래된 기사면 건너뜀 (날짜가 없으면 seen.json이 중복을 막아 줌)
            if published and published < since:
                continue
            topic = best_topic(topics, f"{entry.title} {entry.get('summary', '')}", feed_info["lang"])
            if topic is None:
                continue
            items.append({
                "source": "rss",
                # 기사 링크를 ID로 사용 (사이트가 달라도 겹치지 않음)
                "id": entry.link,
                "topic_id": topic["id"],
                "title": " ".join(entry.title.split()),
                # 기사는 저자 정보가 없는 경우가 많아 빈 리스트로 둠
                "authors": [],
                "link": entry.link,
                "published": published.date().isoformat() if published else "",
                # 신문에 표시할 매체 이름
                "venue": feed_info["name"],
                # 요약문: AI 요약에만 쓰고 저장하지 않음
                "abstract": clean_text(entry.get("summary", "")),
            })
            found += 1
        print(f"{feed_info['name'][:28]:28} {found:3}건 / 전체 {len(feed.entries)}건 (RSS)")
    return items
    # → 피드마다 다룰 주제를 좁혀서, 엉뚱한 주제에 기사가 붙는 일을 줄이겠다


# ===== CLI =====
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="기관·언론 RSS에서 최근 기사 수집")
    parser.add_argument("--days", type=int, default=1, help="최근 며칠 (기본 1)")
    parser.add_argument("--all", action="store_true", help="관심(★) 주제가 아닌 것도 포함")
    args = parser.parse_args()

    items = collect(days=args.days, star_only=not args.all)
    print(f"\n총 {len(items)}건")
    for it in items[:12]:
        print(f"- [{it['topic_id']}] {it['title']} ({it['venue']})")
