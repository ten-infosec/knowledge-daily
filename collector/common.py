"""여러 수집기가 함께 쓰는 설정과 함수.

모든 수집기는 항목을 같은 모양의 딕셔너리로 돌려준다:
  {"source": "arxiv", "id": "2610.26223", "topic_id": "QNT-01",
   "title": ..., "authors": [...], "link": ..., "published": "2026-10-19"}
  → 모양이 같아서 seen.py(중복 방지)와 digest.py(신문 만들기)가 출처를 신경 쓰지 않아도 된다.
"""

# ===== Imports =====
# json: taxonomy.json을 파이썬 리스트로 읽기 위해 사용
import json
# Path: 파일 경로를 다루는 도구
from pathlib import Path

# ===== Settings =====
# 우리가 누구인지 알려주는 이름표. 문제가 생기면 상대 서버가 연락할 수 있게 저장소 주소를 넣음
USER_AGENT = "knowledge-daily/0.1 (+https://github.com/ten-infosec/knowledge-daily)"
# 이 파일 기준으로 프로젝트 최상위 폴더 안의 taxonomy.json 경로
TAXONOMY_PATH = Path(__file__).resolve().parent.parent / "data" / "taxonomy.json"


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
