# -*- coding: utf-8 -*-
"""
g2b_spec.py — RFP(제안요청서/과업지시서) 원문에서 '제안서 작성 기준'(정성 작성 규격) 추출.
정량(회사 스펙 채점)과 별개. RFP 텍스트만 있으면 됨 → 자사 데이터 불필요.
뽑는 것: 판형·매수(장수)·단/양면·표지·목차·쪽번호·글꼴·제출부수·제출방법·유의사항·정성 평가배점.
"""
import re

# 앵커: 이 단어가 있는 줄 주변을 '제안서 작성 규격'으로 간주
ANCHORS = [
    r"제안서\s*작성", r"작성\s*요령", r"작성\s*방법", r"작성\s*지침", r"작성\s*시\s*유의",
    r"제안서\s*규격", r"제안서\s*제출", r"제출\s*방법", r"제출\s*부수", r"제출\s*서류",
    r"규\s*격", r"판\s*형", r"A4", r"A3", r"양\s*면", r"단\s*면",
    r"\d+\s*매\s*이내", r"\d+\s*페이지", r"\d+\s*쪽", r"면\s*수", r"매\s*수",
    r"표\s*지", r"목\s*차", r"쪽\s*번호", r"글\s*꼴", r"글\s*자\s*크기", r"폰\s*트",
    r"유의\s*사항", r"주의\s*사항", r"평가\s*항목", r"평가\s*배점", r"배\s*점",
    r"정성\s*평가", r"기술\s*평가",
]
ANCH_RE = re.compile("|".join(ANCHORS))
# 정성 규격과 무관한 노이즈 줄(입찰·계약 일반)은 컷
DROP = re.compile(r"입찰보증금|계약보증금|지체상금|청렴|부가가치세|낙찰자|적격심사|전자입찰|나라장터\s*이용")

def extract_spec(text, max_lines=40):
    if not text:
        return []
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines()]
    hits = []
    seen = set()
    for i, ln in enumerate(lines):
        if len(ln) < 4:
            continue
        if ANCH_RE.search(ln) and not DROP.search(ln):
            key = ln[:60]
            if key in seen:
                continue
            seen.add(key)
            hits.append(ln)
    # 너무 길면 상위 max_lines
    return hits[:max_lines]

if __name__ == "__main__":
    import os, sys, g2b_rfp
    key = os.environ.get("SERVICE_KEY", "").strip()
    kw = sys.argv[1] if len(sys.argv) > 1 else "구석기전망대"
    no = sys.argv[2] if len(sys.argv) > 2 else None
    it = g2b_rfp.find_by_name(kw, key, no)
    if not it:
        print("공고 없음"); sys.exit(1)
    print("공고:", it.get("bidNtceNm"))
    res = g2b_rfp.get_rfp_text(it, key)
    if not res.get("text"):
        print("RFP 텍스트 없음:", res.get("branch")); sys.exit(0)
    print("추출 글자수:", len(res["text"]))
    print("\n=== 제안서 작성 기준 후보 ===")
    for ln in extract_spec(res["text"]):
        print(" •", ln[:110])
