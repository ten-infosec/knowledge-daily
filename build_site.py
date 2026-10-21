"""GitHub Pages에 올릴 사이트 폴더(_site/)를 만든다.

  _site/
  ├── index.html, style.css, app.js   ← site/ 폴더 그대로
  └── data/
      ├── index.json                 ← 신문 날짜 목록 (최신이 앞)
      ├── taxonomy.json              ← 주제 이름·영역
      └── digests/YYYY-MM-DD.json    ← 하루치 글
"""

# ===== Imports =====
# json: 날짜 목록(index.json)을 씀
import json
# shutil: 폴더·파일 복사와 삭제
import shutil
# Path: 파일 경로를 다루는 도구
from pathlib import Path

# ===== Settings =====
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "_site"


# ===== Build =====
def build():
    # 예전에 만든 _site가 있으면 지우고 새로 만듦 (ignore_errors: 없어도 오류 없음)
    shutil.rmtree(OUT, ignore_errors=True)
    # copytree: site/ 폴더 전체를 _site/로 복사
    shutil.copytree(ROOT / "site", OUT)
    digests_out = OUT / "data" / "digests"
    digests_out.mkdir(parents=True)
    shutil.copy(ROOT / "data" / "taxonomy.json", OUT / "data" / "taxonomy.json")

    # digests/의 하루치 JSON만 복사 (Markdown은 저장소에서 보면 되므로 제외)
    dates = []
    for path in sorted((ROOT / "digests").glob("*.json")):
        shutil.copy(path, digests_out / path.name)
        # path.stem: 확장자를 뺀 파일 이름 (예: 2026-10-22)
        dates.append(path.stem)
    # reverse=True: 최신 날짜가 앞에 오게
    dates.sort(reverse=True)
    (OUT / "data" / "index.json").write_text(json.dumps({"dates": dates}), encoding="utf-8")
    print(f"_site 생성: 신문 {len(dates)}일치")
    # → 저장소의 신문 데이터와 웹 페이지 파일을 한 폴더에 모아, Pages가 그대로 올리게 하겠다


if __name__ == "__main__":
    build()
