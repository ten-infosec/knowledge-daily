"""여러 수집기가 함께 쓰는 설정과 함수.

모든 수집기는 항목을 같은 모양의 딕셔너리로 돌려준다:
  {"source": "arxiv", "id": "2610.26223", "topic_id": "QNT-01",
   "title": ..., "authors": [...], "link": ..., "published": "2026-10-19"}
  → 모양이 같아서 seen.py(중복 방지)와 digest.py(신문 만들기)가 출처를 신경 쓰지 않아도 된다.
"""

# ===== Imports =====
# json: taxonomy.json을 파이썬 리스트로 읽기 위해 사용
import json
# re: 정규식으로 글 속 키워드를 단어 단위로 찾기 위해 사용
import re
# Path: 파일 경로를 다루는 도구
from pathlib import Path

# ===== Settings =====
# 우리가 누구인지 알려주는 이름표. 문제가 생기면 상대 서버가 연락할 수 있게 저장소 주소를 넣음
USER_AGENT = "knowledge-daily/0.1 (+https://github.com/ten-infosec/knowledge-daily)"
# 이 파일 기준으로 프로젝트 최상위 폴더 안의 taxonomy.json 경로
TAXONOMY_PATH = Path(__file__).resolve().parent.parent / "data" / "taxonomy.json"
# 어디에나 자주 나오는 흔한 단어. 이런 단어만 맞은 글은 주제와 관련 없다고 봄
# (예: "key distribution"만 맞은 광석 기사가 "양자 키 분배"에 붙는 것을 막음)
GENERIC_WORDS = {
    "open", "source", "key", "distribution", "tool", "use", "learning", "model",
    "network", "system", "systems", "data", "security", "health", "digital", "small",
    "based", "deep", "science", "software", "physics", "basics", "fundamentals",
}


# ===== Load topics =====
def load_topics(source_name, star_only=True):
    """taxonomy.json에서 수집처(source)에 source_name이 들어 있는 주제만 골라 돌려준다."""
    # encoding="utf-8": 한글이 깨지지 않게 UTF-8로 읽음
    with open(TAXONOMY_PATH, encoding="utf-8") as f:
        topics = json.load(f)
    # 예: source_name="PubMed" → source에 "PubMed"가 있는 주제만
    topics = [t for t in topics if source_name in t["source"]]
    # star_only가 True면 관심(★) 주제만 남김
    if star_only:
        topics = [t for t in topics if t["star"]]
    return topics
    # → 그 수집처에서 찾을 수 있는 주제만 골라, 쓸데없는 요청을 보내지 않겠다


# ===== Match keywords =====
def required_matches(words):
    """키워드 단어 중 몇 개가 글에 들어 있어야 "이 주제다"라고 볼지 정한다.

    단어가 1~2개면 전부, 3개 이상이면 절반 이상(올림).
    예: "lattice-based cryptography" → 2개 모두 / "RSA cryptography integer factorization" → 4개 중 2개
    """
    if len(words) <= 2:
        return len(words)
    # -(-a // b): a를 b로 나눈 값을 올림하는 파이썬 관용구
    return -(-len(words) // 2)


def matched_words(words, text):
    """text 안에 들어 있는 키워드 단어들을 돌려준다 (대소문자 무시)."""
    # re.escape: 단어 속 특수문자(-, . 등)를 글자 그대로 찾게 함
    # (?<![A-Za-z0-9]), (?![A-Za-z0-9]): 앞뒤에 영문·숫자가 붙어 있지 않을 때만
    #   → "AI"가 "said" 안에서는 안 잡히지만, 한글 "AI가"처럼 조사가 붙은 경우는 잡힘
    return [w for w in words
            if re.search(rf"(?<![A-Za-z0-9]){re.escape(w)}(?![A-Za-z0-9])", text, re.IGNORECASE)]


def topic_terms(topic, lang="en"):
    """주제를 찾을 때 쓸 단어 목록. 영어 글은 영문 키워드, 한국어 글은 한글 주제 이름을 쓴다."""
    if lang == "ko":
        # 예: "토카막 핵융합(KSTAR·ITER)" → ["토카막", "핵융합", "KSTAR", "ITER"]
        # re.split: 띄어쓰기·괄호·가운뎃점·쉼표·슬래시를 기준으로 자름
        return [w for w in re.split(r"[\s()·,/]+", topic["topic"]) if w]
    return topic["keywords"].split()


def best_topic(topics, text, lang="en"):
    """text와 가장 잘 맞는 주제를 하나 고른다. 기준을 넘는 주제가 없으면 None."""
    best, best_score = None, 0
    for topic in topics:
        words = topic_terms(topic, lang)
        matched = matched_words(words, text)
        score = len(matched)
        # 맞은 단어가 전부 흔한 단어면 이 주제는 아님
        if all(w.lower() in GENERIC_WORDS for w in matched):
            continue
        # 기준 이상이고, 지금까지 찾은 것보다 더 많이 맞으면 교체
        if score >= required_matches(words) and score > best_score:
            best, best_score = topic, score
    return best
    # → 한 글이 여러 주제에 걸리면 가장 많이 맞는 주제 하나에만 넣겠다
