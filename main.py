"""매일 실행하는 진입점: 수집 → 중복 제거 → 다이제스트 작성 → 기록 저장."""

# ===== Imports =====
# argparse: 터미널 옵션(--days, --dry-run 등)을 읽는 표준 라이브러리
import argparse

# collector/arxiv.py의 collect 함수: arXiv에서 논문 수집
from collector.arxiv import collect as collect_arxiv
# collector/pubmed.py의 collect 함수: PubMed에서 논문 수집
from collector.pubmed import collect as collect_pubmed
# collector/iacr.py의 collect 함수: IACR ePrint에서 암호 논문 수집
from collector.iacr import collect as collect_iacr
# digest.py의 함수들: 다이제스트 Markdown 만들기·저장
from digest import render, today_kst, write_digest
# seen.py의 함수들: 중복 방지 기록 읽기·거르기·저장
from seen import filter_new, load_seen, save_seen


# ===== Main =====
def main():
    parser = argparse.ArgumentParser(description="knowledge-daily 수집 실행")
    # --days: 최근 며칠 동안의 논문 (기본 1)
    parser.add_argument("--days", type=int, default=1, help="최근 며칠 (기본 1)")
    # --all: ★가 아닌 주제까지 포함
    parser.add_argument("--all", action="store_true", help="관심(★) 주제가 아닌 것도 포함")
    # --dry-run: 결과만 보여 주고 seen.json에는 저장하지 않음 (테스트용)
    parser.add_argument("--dry-run", action="store_true", help="파일에 저장하지 않고 결과만 출력")
    args = parser.parse_args()

    # ----- Collect -----
    # 수집기를 차례로 실행해 결과를 한 리스트로 합침
    papers = []
    for collect in (collect_arxiv, collect_pubmed, collect_iacr):
        papers += collect(days=args.days, star_only=not args.all)

    # ----- Dedupe -----
    seen = load_seen()
    new_papers = filter_new(papers, seen)
    print(f"\n수집 {len(papers)}건 → 새 항목 {len(new_papers)}건 (중복 {len(papers) - len(new_papers)}건 제외)")

    # ----- Save -----
    if args.dry_run:
        # 파일은 만들지 않고, 다이제스트 앞부분만 화면에 보여 줌
        print("[dry-run] 저장 생략. 다이제스트 미리보기:\n")
        print("\n".join(render(new_papers, today_kst()).splitlines()[:15]))
        return
    path = write_digest(new_papers)
    print(f"다이제스트 저장: {path.relative_to(path.parent.parent)}")
    save_seen(seen)
    print(f"seen.json 저장 완료 (누적 {len(seen)}건)")
    # → --dry-run 없이 실행하면, 오늘 본 항목이 기록돼 내일은 건너뛰게 하겠다


# 이 파일을 직접 실행했을 때만 main()을 부름
if __name__ == "__main__":
    main()
