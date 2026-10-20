"""arXiv 수집기: taxonomy의 영문 키워드로 최근 N일 동안 올라온 논문을 찾는다.

공식 API(https://info.arxiv.org/help/api/) 만 사용하고, 요청 사이 3초 이상 쉰다.
원문(초록 포함)은 저장하지 않고 제목·저자·링크·날짜만 남긴다.
"""

# ===== Imports =====
# argparse: 터미널에서 넘긴 옵션(--days 등)을 읽는 표준 라이브러리
import argparse
# re: 정규식(문자열 패턴)으로 arXiv ID 끝의 버전 표시를 떼기 위해 사용
import re
# json: taxonomy.json 파일을 파이썬 리스트로 읽기 위해 사용
import json
# time: 요청 사이에 잠깐 멈추는 time.sleep()을 쓰기 위해 사용
import time
# datetime: "지금부터 N일 전"을 계산하기 위해 사용 / timezone.utc: 세계 표준시(UTC)
from datetime import datetime, timedelta, timezone
# Path: 파일 경로를 운영체제와 상관없이 다루는 도구
from pathlib import Path

# feedparser: arXiv가 돌려주는 Atom(XML) 응답을 파이썬 데이터로 바꿔 줌
import feedparser
# requests: arXiv API에 HTTP 요청을 보냄
import requests

# ===== Settings =====
# arXiv API 주소
API_URL = "https://export.arxiv.org/api/query"
# 요청 사이 쉬는 시간(초). arXiv 이용 규칙이 3초 이상
REQUEST_DELAY = 3
# 주제 하나당 가져올 최대 논문 수
MAX_RESULTS = 20
# 우리가 누구인지 알려주는 이름표. 문제가 생기면 arXiv가 연락할 수 있게 저장소 주소를 넣음
USER_AGENT = "knowledge-daily/0.1 (+https://github.com/ten-infosec/knowledge-daily)"
# 이 파일 기준으로 프로젝트 최상위 폴더를 찾고, 그 안의 taxonomy.json 경로를 만듦
TAXONOMY_PATH = Path(__file__).resolve().parent.parent / "data" / "taxonomy.json"
# → 설정값을 맨 위에 모아 두어, 나중에 숫자만 바꾸면 동작을 조절할 수 있게 하겠다


# ===== Load topics =====
def load_arxiv_topics(star_only=True):
    """taxonomy.json에서 수집처에 arXiv가 들어 있는 주제만 골라 돌려준다."""
    # encoding="utf-8": 한글이 깨지지 않게 UTF-8로 읽음
    with open(TAXONOMY_PATH, encoding="utf-8") as f:
        topics = json.load(f)
    # source 문자열에 "arXiv"가 있는 주제만 남김
    topics = [t for t in topics if "arXiv" in t["source"]]
    # star_only가 True면 관심(★) 주제만 남김
    if star_only:
        topics = [t for t in topics if t["star"]]
    return topics
    # → arXiv에서 찾을 수 있는 주제만 골라, 쓸데없는 요청을 보내지 않겠다


# ===== Build query =====
def build_query(words, start, end):
    """키워드 단어들과 기간으로 arXiv 검색식을 만든다."""
    # all:단어 → 제목·초록·저자 등 전체에서 그 단어를 찾음. AND로 묶어 모든 단어가 들어간 논문만
    keyword_part = " AND ".join(f"all:{w}" for w in words)
    # submittedDate:[시작 TO 끝] → 그 기간에 제출된 논문만. 형식은 YYYYMMDDHHMM (UTC)
    date_part = f"submittedDate:[{start:%Y%m%d%H%M} TO {end:%Y%m%d%H%M}]"
    return f"({keyword_part}) AND {date_part}"
    # → 예: (all:neural AND all:decoding) AND submittedDate:[202610200000 TO 202610210000]


# ===== Fetch arXiv =====
def search(query, max_results=MAX_RESULTS):
    """검색식 하나로 arXiv에 요청을 보내고, 논문 목록을 돌려준다."""
    params = {
        # 검색식
        "search_query": query,
        # 최대 몇 건까지 받을지
        "max_results": max_results,
        # 제출일 기준 최신순 정렬
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    # timeout=30: 30초 안에 응답이 없으면 포기 (프로그램이 멈춰 있지 않게)
    response = requests.get(API_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=30)
    # 응답 코드가 오류(4xx, 5xx)면 바로 예외를 일으켜 알려 줌
    response.raise_for_status()
    # Atom XML 텍스트를 feedparser로 해석
    feed = feedparser.parse(response.text)

    papers = []
    for entry in feed.entries:
        papers.append({
            # entry.id 예: http://arxiv.org/abs/2610.12345v1 → "/abs/" 뒤에서 버전(v1)을 뗀 2610.12345만 저장
            "arxiv_id": re.sub(r"v\d+$", "", entry.id.split("/abs/")[-1]),
            # 제목 안의 줄바꿈·여러 칸 공백을 한 칸으로 정리
            "title": " ".join(entry.title.split()),
            # 저자 이름만 리스트로
            "authors": [a.name for a in entry.get("authors", [])],
            # 논문 페이지 링크
            "link": entry.link,
            # 처음 제출된 날짜 (예: 2026-10-20T17:59:59Z)
            "published": entry.published,
            # 분류(예: quant-ph, cs.CR)
            "categories": [t.term for t in entry.get("tags", [])],
        })
    return papers
    # → 초록(summary)은 일부러 저장하지 않겠다 (원문 저장 금지 규칙)


def latest_window(days=1):
    """arXiv에 가장 최근 발표된 논문의 제출 시각을 기준으로 검색 기간(시작, 끝)을 정한다.

    arXiv는 제출된 논문을 하루 한 번 묶어서 발표하므로, 발표 전 논문은 API에 안 보인다.
    그래서 "지금부터 24시간"으로 찾으면 늘 비어 있다. 대신 "마지막 발표분부터 거꾸로 days일"을 쓴다.
    """
    now = datetime.now(timezone.utc)
    # 최근 7일 안에 제출된 논문 중 가장 최신 1건만 요청
    newest = search(f"submittedDate:[{now - timedelta(days=7):%Y%m%d%H%M} TO {now:%Y%m%d%H%M}]", max_results=1)
    # 혹시 아무것도 없으면 지금 시각을 기준으로 함
    if not newest:
        end = now
    else:
        # "2026-10-19T17:59:59Z" 같은 문자열을 datetime으로 바꾸고, 1분 여유를 둠
        end = datetime.fromisoformat(newest[0]["published"]) + timedelta(minutes=1)
    return end - timedelta(days=days), end
    # → 매일 실행했을 때 그날 새로 발표된 논문 묶음을 정확히 잡겠다


def fetch_topic(topic, start, end):
    """주제 하나에 대해 start~end 기간에 제출된 논문을 찾는다."""
    # 영문 키워드를 띄어쓰기 기준으로 단어로 나눔
    words = topic["keywords"].split()

    # 1차: 모든 단어가 들어간 논문 검색
    papers = search(build_query(words, start, end))
    # 결과가 없고 단어가 3개 이상이면, 앞의 2단어로 넓혀서 한 번 더 찾음
    # (예: "quantum algorithm Shor Grover VQE" → "quantum algorithm")
    if not papers and len(words) > 2:
        time.sleep(REQUEST_DELAY)
        papers = search(build_query(words[:2], start, end))

    # 어느 주제에서 찾은 논문인지 표시
    for p in papers:
        p["topic_id"] = topic["id"]
    return papers
    # → 키워드가 길어서 아무것도 안 나오는 경우를 줄이겠다


def collect(days=1, star_only=True):
    """대상 주제를 하나씩 돌며 논문을 모은다. 요청 사이에는 3초씩 쉰다."""
    topics = load_arxiv_topics(star_only)
    # 검색 기간을 먼저 정함 (요청 1회)
    start, end = latest_window(days)
    print(f"검색 기간(UTC): {start:%Y-%m-%d %H:%M} ~ {end:%Y-%m-%d %H:%M}")
    results = []
    for topic in topics:
        # 직전 요청과 3초 간격을 둠
        time.sleep(REQUEST_DELAY)
        try:
            papers = fetch_topic(topic, start, end)
        except requests.RequestException as e:
            # 한 주제가 실패해도 전체가 멈추지 않게, 알리고 다음 주제로 넘어감
            print(f"[warn] {topic['id']} 요청 실패: {e}")
            continue
        print(f"{topic['id']:7} {len(papers):3}건  {topic['topic']}")
        results.extend(papers)
    return results
    # → 주제별 결과를 한 리스트로 모아 돌려주겠다


# ===== CLI =====
# 이 파일을 직접 실행했을 때만 아래 코드가 돎 (다른 파일에서 import할 때는 안 돎)
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="arXiv에서 최근 논문 수집")
    # --days: 며칠 전까지 찾을지 (기본 1일)
    parser.add_argument("--days", type=int, default=1, help="최근 며칠 동안의 논문 (기본 1)")
    # --all: 붙이면 ★가 아닌 주제까지 전부
    parser.add_argument("--all", action="store_true", help="관심(★) 주제가 아닌 것도 포함")
    args = parser.parse_args()

    papers = collect(days=args.days, star_only=not args.all)
    print(f"\n총 {len(papers)}건")
    # 앞의 5건만 미리보기
    for p in papers[:5]:
        print(f"- [{p['topic_id']}] {p['title']}\n  {p['link']}")
    # → 터미널에서 결과를 바로 눈으로 확인할 수 있게 하겠다
