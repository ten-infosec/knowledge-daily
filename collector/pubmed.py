"""PubMed 수집기: 의학·생명과학 논문 데이터베이스 PubMed에서 최근 N일 동안 추가된 논문을 찾는다.

NCBI 공식 API인 E-utilities(https://www.ncbi.nlm.nih.gov/books/NBK25497/)를 사용한다.
  - esearch: 검색어로 논문 번호(PMID) 목록을 받음
  - esummary: PMID로 제목·저자·학술지·날짜를 받음
  - efetch: PMID로 초록을 받음 (AI 요약에만 쓰고 저장하지 않음)
API 키 없이 초당 3회까지 허용되지만, 여유 있게 요청 사이 1초씩 쉰다.
초록은 저장하지 않는다 (원문 저장 금지 규칙).
"""

# ===== Imports =====
# argparse: 터미널 옵션(--days 등)을 읽는 표준 라이브러리
import argparse
# time: 요청 사이에 쉬는 time.sleep()
import time
# ElementTree: efetch가 돌려주는 XML에서 초록을 꺼내기 위해 사용
import xml.etree.ElementTree as ET

# requests: E-utilities에 HTTP 요청을 보냄
import requests

# common.py의 공통 설정·함수: 이름표(User-Agent), 주제 읽기
from collector.common import USER_AGENT, load_topics

# ===== Settings =====
# E-utilities 기본 주소
BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
# 요청 사이 쉬는 시간(초). NCBI 허용치는 초당 3회
REQUEST_DELAY = 1
# 주제 하나당 가져올 최대 논문 수
MAX_RESULTS = 20
# NCBI가 권장하는 "어떤 프로그램이 요청하는지" 표시
TOOL_NAME = "knowledge-daily"


# ===== Request helper =====
def get_json(endpoint, params):
    """E-utilities에 요청을 보내고 JSON 결과를 돌려준다."""
    # retmode=json: XML 대신 JSON으로 받음 / tool: 프로그램 이름
    params = {**params, "retmode": "json", "tool": TOOL_NAME}
    response = requests.get(f"{BASE_URL}/{endpoint}", params=params,
                            headers={"User-Agent": USER_AGENT}, timeout=30)
    # 오류 응답(4xx, 5xx)이면 예외를 일으킴
    response.raise_for_status()
    return response.json()


# ===== Search =====
def build_term(words):
    """단어들을 PubMed 검색식으로 만든다. [tiab] = 제목(title)이나 초록(abstract)에 있는 것만."""
    return " AND ".join(f"{w}[tiab]" for w in words)
    # → 예: neural[tiab] AND decoding[tiab]
    #   [tiab]을 안 붙이면 PubMed가 단어를 넓게 바꿔 찾아서 관련 없는 논문이 많이 섞임


def search_ids(words, days):
    """검색식으로 최근 days일 동안 PubMed에 추가된 논문 번호(PMID) 목록을 받는다."""
    data = get_json("esearch.fcgi", {
        # 검색할 데이터베이스
        "db": "pubmed",
        # 검색식
        "term": build_term(words),
        # reldate: 오늘부터 며칠 전까지 / datetype=edat: PubMed에 추가된 날짜 기준
        "reldate": days,
        "datetype": "edat",
        # 최대 건수 / 최신순
        "retmax": MAX_RESULTS,
        "sort": "pub_date",
    })
    return data["esearchresult"]["idlist"]


def fetch_topic_ids(topic, days):
    """주제 하나의 PMID 목록. 결과가 없고 단어가 3개 이상이면 앞의 2단어로 한 번 더 찾는다."""
    words = topic["keywords"].split()
    ids = search_ids(words, days)
    if not ids and len(words) > 2:
        time.sleep(REQUEST_DELAY)
        ids = search_ids(words[:2], days)
    return ids
    # → arXiv 수집기와 같은 방식으로, 키워드가 길어 0건이 되는 경우를 줄이겠다


# ===== Summaries =====
def fetch_summaries(pmids):
    """PMID 목록으로 제목·저자·학술지·날짜를 한 번에 받아 {PMID: 정보} 딕셔너리로 돌려준다."""
    if not pmids:
        return {}
    # id: 쉼표로 이어 붙인 PMID 목록 (한 번 요청으로 여러 건)
    data = get_json("esummary.fcgi", {"db": "pubmed", "id": ",".join(pmids)})
    result = data["result"]
    # result["uids"]: 응답에 들어 있는 PMID 목록
    return {pmid: result[pmid] for pmid in result.get("uids", [])}


def fetch_abstracts(pmids):
    """PMID 목록의 초록을 한 번에 받아 {PMID: 초록} 딕셔너리로 돌려준다. (efetch는 JSON이 없어 XML로 받음)"""
    if not pmids:
        return {}
    response = requests.get(f"{BASE_URL}/efetch.fcgi",
                            params={"db": "pubmed", "id": ",".join(pmids), "retmode": "xml", "tool": TOOL_NAME},
                            headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()
    # response.content(바이트)를 XML 나무 구조로 해석
    root = ET.fromstring(response.content)
    abstracts = {}
    # 논문 하나 = <PubmedArticle> 하나
    for article in root.iter("PubmedArticle"):
        pmid = article.findtext("MedlineCitation/PMID")
        # 초록은 "목적/방법/결과"처럼 여러 <AbstractText>로 나뉘어 있을 수 있어 이어 붙임
        # itertext(): 태그 안의 글자를 (기울임 같은 안쪽 태그 포함) 전부 꺼냄
        parts = ["".join(t.itertext()) for t in article.iterfind(".//Abstract/AbstractText")]
        abstracts[pmid] = " ".join(" ".join(parts).split())
    return abstracts
    # → 초록 없는 논문은 빈 문자열로 두고, 요약은 제목만 보고 하게 하겠다


# ===== Collect =====
def collect(days=1, star_only=True):
    """대상 주제를 하나씩 검색하고, 찾은 논문의 정보를 모아 공통 형식으로 돌려준다."""
    topics = load_topics("PubMed", star_only)
    # (PMID, 주제 id) 쌍을 모아 둠
    hits = []
    for i, topic in enumerate(topics):
        if i > 0:
            time.sleep(REQUEST_DELAY)
        try:
            ids = fetch_topic_ids(topic, days)
        except requests.RequestException as e:
            # 한 주제가 실패해도 나머지는 계속
            print(f"[warn] {topic['id']} PubMed 요청 실패: {e}")
            continue
        print(f"{topic['id']:7} {len(ids):3}건  {topic['topic']} (PubMed)")
        hits += [(pmid, topic["id"]) for pmid in ids]

    # 모든 PMID의 정보를 한 번에 요청 (중복 PMID는 dict.fromkeys로 한 번만)
    time.sleep(REQUEST_DELAY)
    try:
        summaries = fetch_summaries(list(dict.fromkeys(pmid for pmid, _ in hits)))
    except requests.RequestException as e:
        print(f"[warn] PubMed 정보 요청 실패: {e}")
        return []
    # 초록도 한 번에 요청. 실패하거나 XML이 깨져도 제목·링크는 그대로 쓰고 초록만 비움
    time.sleep(REQUEST_DELAY)
    try:
        abstracts = fetch_abstracts(list(summaries))
    except (requests.RequestException, ET.ParseError) as e:
        print(f"[warn] PubMed 초록 요청 실패 (초록 없이 계속): {e}")
        abstracts = {}

    papers = []
    for pmid, topic_id in hits:
        s = summaries.get(pmid)
        # 정보를 못 받은 PMID는 건너뜀
        if not s:
            continue
        papers.append({
            "source": "pubmed",
            "id": pmid,
            "topic_id": topic_id,
            "title": s["title"].rstrip("."),
            "authors": [a["name"] for a in s.get("authors", [])],
            "link": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            # sortpubdate 예: "2026/10/15 00:00" → "2026-10-15"
            "published": s.get("sortpubdate", "")[:10].replace("/", "-"),
            # 학술지 이름 (예: Optics letters)
            "venue": s.get("fulljournalname", ""),
            # 초록: AI 요약에만 쓰고 저장하지 않음
            "abstract": abstracts.get(pmid, ""),
        })
    return papers
    # → 주제별 검색은 따로, 정보 요청은 한 번에 묶어 요청 횟수를 줄이겠다


# ===== CLI =====
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PubMed에서 최근 논문 수집")
    parser.add_argument("--days", type=int, default=1, help="최근 며칠 (기본 1)")
    parser.add_argument("--all", action="store_true", help="관심(★) 주제가 아닌 것도 포함")
    args = parser.parse_args()

    papers = collect(days=args.days, star_only=not args.all)
    print(f"\n총 {len(papers)}건")
    for p in papers[:5]:
        print(f"- [{p['topic_id']}] {p['title']} ({p['venue']})\n  {p['link']}")
