"""중복 방지: 이미 수집한 항목의 ID를 state/seen.json에 기록해 두고, 다음 실행 때 건너뛴다.

seen.json 형식: {"arxiv:2610.26223": "2026-10-21", ...}
  → 키는 "출처:ID", 값은 처음 본 날짜 (나중에 오래된 기록을 지울 때 사용)
"""

# ===== Imports =====
# json: seen.json을 읽고 쓰기 위해 사용
import json
# date: 오늘 날짜를 기록하기 위해 사용
from datetime import date
# Path: 파일 경로를 다루는 도구
from pathlib import Path

# ===== Settings =====
# 이 파일과 같은 폴더(프로젝트 최상위) 아래 state/seen.json
SEEN_PATH = Path(__file__).resolve().parent / "state" / "seen.json"


# ===== Load / save =====
def load_seen():
    """seen.json을 읽어 딕셔너리로 돌려준다. 파일이 없으면 빈 딕셔너리."""
    # 첫 실행이라 파일이 아직 없으면 빈 기록으로 시작
    if not SEEN_PATH.exists():
        return {}
    with open(SEEN_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_seen(seen):
    """seen 딕셔너리를 seen.json에 저장한다."""
    # parents=True: 중간 폴더(state/)가 없으면 함께 만듦 / exist_ok=True: 이미 있어도 오류 없음
    SEEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SEEN_PATH, "w", encoding="utf-8") as f:
        # ensure_ascii=False: 한글을 \uXXXX가 아닌 글자 그대로 저장 / indent=1: 사람이 읽기 쉽게 줄바꿈
        # sort_keys=True: 키 순서를 고정해 Git에서 바뀐 줄만 깔끔하게 보이게 함
        json.dump(seen, f, ensure_ascii=False, indent=1, sort_keys=True)
        # 파일 끝에 줄바꿈 하나 (Git 경고 방지)
        f.write("\n")
    # → 매 실행 결과가 Git 기록으로 남아, 언제 무엇을 처음 봤는지 추적할 수 있겠다


# ===== Filter =====
def filter_new(items, seen, source):
    """seen에 없는 항목만 돌려주고, 돌려준 항목은 seen에 추가한다.

    같은 논문이 여러 주제에 동시에 걸린 경우에도 처음 한 번만 남는다.
    """
    today = date.today().isoformat()
    new_items = []
    for item in items:
        # 예: "arxiv:2610.26223"
        key = f"{source}:{item['arxiv_id']}"
        # 이미 본 항목이면 건너뜀
        if key in seen:
            continue
        # 처음 보는 항목이면 기록하고 결과에 넣음
        seen[key] = today
        new_items.append(item)
    return new_items
    # → 어제 본 논문이 오늘 또 나오거나, 한 논문이 두 주제에 겹쳐 나오는 일을 막겠다
