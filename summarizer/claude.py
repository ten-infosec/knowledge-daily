"""AI 요약·선별: 주제마다 Claude에게 그날 후보를 보여 주고, 읽을 만한 1~2건을 골라 한국어로 요약받는다.

주제 하나 = API 호출 1번. Claude가 한 번에 돌려주는 것:
  - 주제와 실제로 관련 있는 상위 1~2건 (키워드만 겹친 엉뚱한 글은 빠짐)
  - 같은 소식을 다룬 다른 글 묶음 (중복 제거)
  - 3줄 한국어 요약, 난이도(입문/중급/심화), 읽을 이유, 중요도(1~5)

초록은 이 요청에만 쓰고 저장하지 않는다. 저장되는 것은 Claude가 새로 쓴 요약뿐이다.
ANTHROPIC_API_KEY가 없으면 아무것도 하지 않는다 (요약 없이 제목·링크만 있는 신문이 그대로 나옴).
"""

# ===== Imports =====
# json: Claude가 돌려준 JSON 글자를 파이썬 데이터로 바꿈
import json
# os: 환경변수(ANTHROPIC_API_KEY)를 읽음
import os
# Path: .env 파일 경로를 다룸
from pathlib import Path

# anthropic: Anthropic 공식 파이썬 SDK (Claude API 호출)
import anthropic

# ===== Settings =====
# 사용할 모델. 비용을 줄이려면 "claude-haiku-5-5"로 바꿀 수 있음 (README 참고)
MODEL = "claude-opus-5-5"
# effort: 얼마나 깊이 생각할지. 요약·선별은 어렵지 않은 일이라 "low"로 비용을 아낌
EFFORT = "low"
# 응답 최대 길이(토큰). 요약 2건 정도라 넉넉함
MAX_TOKENS = 16000
# 주제당 최대로 고를 건수
MAX_PICKS = 2
# 후보 하나의 초록을 몇 글자까지 보낼지 (긴 RSS 본문 미리보기 등으로 요청이 커지지 않게)
MAX_ABSTRACT_CHARS = 2000
# 프로젝트 최상위 폴더의 .env (로컬 실행용. GitHub Actions에서는 Secrets가 환경변수로 들어옴)
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

# 시스템 프롬프트: 매번 똑같이 보내는 역할·규칙 설명
SYSTEM_PROMPT = """당신은 매일 아침 "지식 신문"을 만드는 편집자입니다.
독자는 한국의 헬스케어 AI 부트캠프 수강생으로, 웹/앱·AI 개발자를 지망하며 과학·기술 전반에 관심이 많습니다.

한 주제에 대해 오늘 수집된 후보 글(논문·기사) 목록을 받으면:
1. 그 주제를 실제로 다루는 글만 고릅니다. 검색 키워드가 우연히 겹친 글은 고르지 않습니다. 맞는 글이 없으면 picks를 빈 목록으로 둡니다.
2. 그중 독자가 읽을 가치가 가장 큰 글을 최대 2개 고릅니다.
3. 고른 글과 같은 연구·같은 소식을 다룬 다른 후보가 있으면 그 번호를 same_as에 넣습니다.
4. 고른 글마다:
   - summary: 한국어 문장 정확히 3개. 무엇을 했는지, 어떻게 했는지, 왜 중요한지. 전문 용어는 처음 나올 때 쉬운 말로 풀어 씁니다.
   - difficulty: "입문"(배경지식 없이 읽힘), "중급"(전공 기초 필요), "심화"(해당 분야 전문 지식 필요) 중 하나.
   - why: 이 독자가 읽으면 좋은 이유 한 문장 (한국어).
   - importance: 1~5 정수. 그 분야에서 얼마나 중요한 소식인지.
후보에 없는 사실을 지어내지 말고, 제목과 초록에 있는 내용만 바탕으로 씁니다."""

# 응답 형식(JSON 스키마). output_config.format으로 넘기면 Claude가 이 모양의 JSON만 돌려줌
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "picks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    # 후보 번호 ([0], [1], ...)
                    "index": {"type": "integer"},
                    # 같은 소식을 다룬 다른 후보 번호들
                    "same_as": {"type": "array", "items": {"type": "integer"}},
                    "summary": {"type": "array", "items": {"type": "string"}},
                    "difficulty": {"type": "string", "enum": ["입문", "중급", "심화"]},
                    "why": {"type": "string"},
                    "importance": {"type": "integer"},
                },
                "required": ["index", "same_as", "summary", "difficulty", "why", "importance"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["picks"],
    "additionalProperties": False,
}
# → 응답 모양을 고정해 두어, 코드가 매번 같은 방식으로 결과를 읽을 수 있게 하겠다


# ===== API key =====
def load_api_key():
    """ANTHROPIC_API_KEY를 찾는다. 환경변수가 없으면 로컬 .env 파일에서 읽는다. 없으면 None."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"]
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            # "이름=값" 형태의 줄만 읽음. partition: 첫 "=" 기준으로 앞·뒤를 나눔
            name, _, value = line.partition("=")
            if name.strip() == "ANTHROPIC_API_KEY" and value.strip():
                return value.strip()
    return None
    # → 키를 코드에 쓰지 않고, 환경변수나 .env(로컬, Git에 안 올라감)에서만 가져오겠다


# ===== Prompt =====
def build_prompt(topic, candidates):
    """주제 설명 + 번호 붙인 후보 목록을 Claude에게 보낼 글로 만든다."""
    lines = [
        f"주제: {topic['topic']} ({topic['id']}, 영역: {topic['area']})",
        f"검색 키워드: {topic['keywords']}",
        "",
        "후보:",
    ]
    for i, item in enumerate(candidates):
        where = item.get("venue") or item["source"]
        abstract = item.get("abstract", "")[:MAX_ABSTRACT_CHARS] or "(초록 없음)"
        lines += [f"[{i}] {item['title']}", f"    출처: {where}", f"    초록: {abstract}", ""]
    return "\n".join(lines)


# ===== Call Claude =====
def ask_claude(client, topic, candidates):
    """주제 하나에 대해 Claude를 한 번 호출하고, picks 목록(딕셔너리들)을 돌려준다."""
    # beta.messages.create: fallbacks 같은 베타 기능을 쓰기 위한 호출
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        # fallbacks="default": 안전 필터가 요청을 거절하면, Anthropic이 권하는 다른 모델로 서버에서 자동 재시도
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_prompt(topic, candidates)}],
        # effort: 생각 깊이 / format: 위의 JSON 스키마 모양으로만 답하게 함
        output_config={
            "effort": EFFORT,
            "format": {"type": "json_schema", "schema": RESPONSE_SCHEMA},
        },
    )
    # 거절(refusal)이면 내용이 없거나 불완전하므로 이 주제는 요약 없이 넘어감
    if response.stop_reason == "refusal":
        raise RuntimeError(f"Claude가 요청을 거절함 ({getattr(response.stop_details, 'category', None)})")
    # 응답이 max_tokens에서 잘렸으면 JSON이 깨져 있을 수 있음
    if response.stop_reason == "max_tokens":
        raise RuntimeError("응답이 너무 길어 잘림")
    # 응답 안의 text 블록에 JSON이 들어 있음 (thinking 블록 등은 건너뜀)
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)["picks"]
    # → 거절·잘림은 오류로 알려서, 그 주제만 요약 없이 신문에 들어가게 하겠다


# ===== Summarize =====
def summarize(items, topics):
    """새 항목들에 요약·선별 결과를 붙여 돌려준다. 키가 없으면 그대로 돌려준다.

    결과 표시 (digest.py가 읽음):
      - 고른 글: item["pick"] = {"summary": [...], "difficulty", "why", "importance", "related": [...]}
      - 같은 소식이라 묶인 글: item["dup_of"] = 고른 글의 "출처:ID"
      - 요약을 거쳤지만 고르지 않은 글: item["summarized"] = True 만 붙음
      - 요약 실패한 주제의 글: 아무것도 안 붙음 (요약 없이 제목·링크만 나옴)
    """
    api_key = load_api_key()
    if not api_key:
        print("[info] ANTHROPIC_API_KEY 없음 → AI 요약 건너뜀")
        return items
    # max_retries=3: 429(요청 너무 많음)·5xx·연결 오류는 SDK가 알아서 3번까지 다시 시도
    client = anthropic.Anthropic(api_key=api_key, max_retries=3)
    topic_by_id = {t["id"]: t for t in topics}

    # 주제별로 후보를 묶음
    by_topic = {}
    for item in items:
        by_topic.setdefault(item["topic_id"], []).append(item)

    for topic_id, candidates in by_topic.items():
        topic = topic_by_id.get(topic_id)
        if topic is None:
            continue
        try:
            picks = ask_claude(client, topic, candidates)
        except (anthropic.APIError, RuntimeError, json.JSONDecodeError, KeyError, StopIteration) as e:
            # 한 주제가 실패해도 다른 주제는 계속. 이 주제 글들은 요약 없이 신문에 들어감
            print(f"[warn] {topic_id} 요약 실패, 요약 없이 계속: {e}")
            continue

        # 이 주제의 후보는 모두 "요약을 거침"으로 표시
        for item in candidates:
            item["summarized"] = True
        # 번호가 범위 안에 있는 것만, 최대 MAX_PICKS건
        valid = [p for p in picks if 0 <= p["index"] < len(candidates)][:MAX_PICKS]
        for p in valid:
            picked = candidates[p["index"]]
            # 앞에서 고른 글의 "같은 소식"으로 이미 묶였으면 따로 고르지 않음
            if "dup_of" in picked:
                continue
            # 같은 소식으로 묶인 글: 고른 글의 "관련 글"로 넣고, 따로 표시하지 않게 dup_of를 붙임
            related = []
            for j in p["same_as"]:
                if 0 <= j < len(candidates) and j != p["index"] and "pick" not in candidates[j]:
                    dup = candidates[j]
                    dup["dup_of"] = f"{picked['source']}:{picked['id']}"
                    related.append({"title": dup["title"], "link": dup["link"],
                                    "venue": dup.get("venue") or dup["source"]})
            picked["pick"] = {
                # 3줄만 사용 (혹시 더 길게 오면 자름)
                "summary": p["summary"][:3],
                "difficulty": p["difficulty"],
                "why": p["why"],
                # 1~5 범위로 맞춤
                "importance": max(1, min(5, p["importance"])),
                "related": related,
            }
        print(f"{topic_id:7} 후보 {len(candidates):3}건 → 선택 {len(valid)}건")
    return items
    # → 신문에는 고른 글의 요약이 먼저, 나머지는 접힌 목록으로 들어가게 하겠다
