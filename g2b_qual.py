#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
g2b_qual.py — 제안요청서·공고문 원문에서 '입찰참가자격'을 규칙 기반으로 태깅한다.
목적: 대시보드의 「우리 보유 자격 체크 → 참가 가능 공고만 보기」(v2.4) 필터를
      **매일 배치에서 자동으로** 채우는 것. 사람·LLM 손을 타지 않아도 새 공고에 태그가 붙는다.

핵심 설계 — 왜 '원문 참가자격 절'만 보는가
  2026-07-30에 리포트 산문(요약문)에서 정규식으로 뽑았더니 오탐이 쏟아졌다.
    · 발주기관 소재지("부산광역시가 발주")를 지역제한으로 오인
    · 참가 가능 대상으로 열거된 "연구기관"을 법인유형 한정으로 오인
  → 그래서 이 모듈은 **「입찰참가자격」 표제 이후의 구간만** 잘라서 본다(실측 34/35 파일에 표제 존재).
     지역제한·공동수급 판정도 그 구간 안에서만 한다.

출력 스키마 (qualifications.json 의 items 값과 동일)
  {"req": [태그id...], "region_limit": "경상남도"|"", "consortium": "허용"|"불허"|"", "confidence": "확실"|"불확실"}
"""
import re

# ── 태그 사전 (id → 표시명). qualifications.json 의 tags 와 반드시 동일하게 유지 ──
TAGS = {
    "sd_ind":    "산업디자인전문회사",
    "video":     "비디오물제작업",
    "sw":        "소프트웨어사업자",
    "ict":       "정보통신공사업",
    "interior":  "실내건축공사업",
    "elec":      "전기공사·설계업",
    "eng_urban": "엔지니어링·기술사(도시계획)",
    "eng_land":  "엔지니어링·기술사(조경)",
    "eng_other": "엔지니어링·기술사(기타)",
    "arch":      "건축사사무소",
    "survey":    "측량업",
    "academic":  "학술연구용역 업종",
    "dpc":       "직접생산확인증명서",
    "smebiz":    "중소·소기업 확인",
    "org_type":  "법인유형 한정(사회적기업 등)",
}

# ── 참가자격 절 잘라내기 ────────────────────────────────────────────────
# 표제 뒤 SECTION_LEN 자를 자격 구간으로 본다. 다음 장 표제가 먼저 나오면 거기서 끊는다.
SEC_HEAD = re.compile(
    r"(입\s*찰\s*참\s*가\s*자\s*격|참\s*가\s*자\s*격|자\s*격\s*요\s*건|참가등록\s*자격)")
SEC_STOP = re.compile(
    r"(공동수급에\s*관한|제안서\s*평가|평가\s*방법|낙찰자\s*결정|계약\s*체결|과업\s*내용|과업의\s*범위)")
SECTION_LEN = 2600


def qual_section(text):
    """참가자격 관련 구간을 모두 이어붙여 돌려준다. 표제를 못 찾으면 빈 문자열."""
    if not text:
        return ""
    parts = []
    for m in SEC_HEAD.finditer(text):
        seg = text[m.start(): m.start() + SECTION_LEN]
        stop = SEC_STOP.search(seg, 60)          # 표제 직후 60자는 건너뛰고 탐색
        parts.append(seg[: stop.start()] if stop else seg)
        if len(parts) >= 6:                       # 표제가 반복되는 문서 방어
            break
    return "\n".join(parts)


# ── 업종·면허 패턴 ─────────────────────────────────────────────────────
# 값은 (필수 패턴, 제외 패턴). 제외 패턴이 같은 줄에 있으면 태그하지 않는다(가점·우대 컷).
REQ_PAT = [
    ("sd_ind",   r"(산업디자인\s*전문\s*회사|공공디자인\s*전문\s*회사|디자인\s*전문\s*회사|444[24]|6484)"),
    ("video",    r"(비디오물\s*제작업|3244)"),
    ("sw",       r"(소프트웨어\s*사업자|소프트웨어사업자\s*신고|1468|1469)"),
    ("ict",      r"정보통신\s*공사업"),
    ("interior", r"실내건축\s*공사업"),
    ("elec",     r"(전력기술관리법|전기\s*설계업|전기공사업)"),
    ("arch",     r"(건축사\s*사무소|4817)"),
    ("survey",   r"측량업"),
    ("academic", r"(학술연구용역|1169|1269)"),
    ("dpc",      r"직접\s*생산\s*확인"),
    ("smebiz",   r"(중소기업\s*확인|소기업\s*확인|중소기업자간\s*경쟁|소기업·?소상공인|중소기업\s*여부)"),
    ("org_type", r"(사회적기업|협동조합|마을기업|비영리\s*법인)[^\n]{0,40}(만|한정|에\s*한|으로\s*제한)"),
]
# 엔지니어링·기술사는 분야를 함께 봐야 한다
ENG_HEAD = r"(엔지니어링\s*사업(자|\s*신고)?|기술사\s*사무소)"
ENG_FIELD = [("eng_urban", r"도시\s*계획"), ("eng_land", r"조경")]

# 가점·우대 문맥이면 필수로 보지 않는다
SOFT_CTX = re.compile(r"(가점|우대|권장|있으면\s*좋|바람직|참고)")


def _line_ok(seg, m):
    """매칭이 '가점·우대' 줄에 있으면 False."""
    ls = seg.rfind("\n", 0, m.start()) + 1
    le = seg.find("\n", m.end())
    line = seg[ls: le if le > 0 else len(seg)]
    return not SOFT_CTX.search(line)


def extract_req(seg):
    req = []
    for tag, pat in REQ_PAT:
        for m in re.finditer(pat, seg):
            if _line_ok(seg, m):
                req.append(tag)
                break
    for m in re.finditer(ENG_HEAD, seg):
        if not _line_ok(seg, m):
            continue
        near = seg[max(0, m.start() - 60): m.end() + 60]
        fields = [t for t, fp in ENG_FIELD if re.search(fp, near)]
        req.extend(fields or ["eng_other"])
    # 중복 제거(순서 유지)
    return list(dict.fromkeys(req))


# ── 지역제한 ───────────────────────────────────────────────────────────
SIDO = ("서울특별시|부산광역시|대구광역시|인천광역시|광주광역시|대전광역시|울산광역시|세종특별자치시|"
        "경기도|강원특별자치도|강원도|충청북도|충청남도|전라북도|전북특별자치도|전라남도|"
        "경상북도|경상남도|제주특별자치도")
# '본점·주사무소가 …에 있는 업체' 형태만 잡는다. 발주기관 표기는 이 구문을 만들지 않는다.
REGION_PAT = re.compile(
    r"(본\s*점|주\s*사무소|본사|법인등기부[^\n]{0,10}소재지)[^\n]{0,40}?(" + SIDO + r")"
    r"|(" + SIDO + r")[^\n]{0,24}(에\s*본\s*점|내에\s*본\s*점|소재\s*업체|소재하는\s*업체|"
    r"에\s*주\s*사무소|지역\s*업체로\s*제한|업체로\s*제한|내에\s*사업장|에\s*사업장을|"
    r"내\s*업체|에\s*소재하고|관내\s*업체|내에\s*소재)")


def extract_region(seg):
    m = REGION_PAT.search(seg)
    if not m:
        return ""
    for g in m.groups():
        if g and re.fullmatch(SIDO, g):
            return g
    return ""


# ── 공동수급 ───────────────────────────────────────────────────────────
CONS_NO = re.compile(r"(공동\s*(수급|도급|계약)[^\n]{0,30}(불가|금지|불허|허용하지|인정하지|제외)"
                     r"|단독\s*(이행|입찰|도급|참가|응찰)만|컨소시엄[^\n]{0,14}(불가|금지|불허)"
                     r"|공동수급체\s*구성[^\n]{0,14}(불가|금지)"
                     r"|단독\s*계약|하도급\s*및\s*공동수급[^\n]{0,14}(불가|금지))")
CONS_OK = re.compile(r"(분담\s*이행|공동\s*이행"
                     r"|공동\s*(수급|도급|계약)[^\n]{0,24}(가능|허용|인정|할\s*수\s*있))")


def extract_cons(seg):
    if CONS_NO.search(seg):
        return "불허"
    if CONS_OK.search(seg):
        return "허용"
    return ""


# ── 공개 API ───────────────────────────────────────────────────────────
# 아래 3종은 참가자격 절 밖(총칙·유의사항·별지)에 적히는 일이 흔해 전문(全文)에서 찾는다.
# 대신 패턴을 아주 좁게 잡아 '발주기관 소재지'류 오탐이 원리상 생기지 않게 한다.
SME_WIDE = re.compile(r"(중소기업자간\s*경쟁|중소기업\s*확인서|소기업[·,\s]*소상공인\s*확인서"
                      r"|중소기업\s*제품\s*구매촉진|소기업\s*확인서|중소기업\s*여부\s*확인)")


def extract_qual(text):
    """RFP·공고문 원문 → 자격 태그 dict. 참가자격 절을 못 찾으면 confidence='불확실'."""
    seg = qual_section(text)
    body = text or ""
    if not seg:
        # 절을 못 찾아도 전문 기반 3종은 시도하되 불확실로 표기한다
        return {"req": (["smebiz"] if SME_WIDE.search(body) else []),
                "region_limit": extract_region(body),
                "consortium": extract_cons(body),
                "confidence": "불확실"}
    req = extract_req(seg)
    if "smebiz" not in req and SME_WIDE.search(body):
        req.append("smebiz")
    return {"req": req,
            "region_limit": extract_region(seg) or extract_region(body),
            "consortium": extract_cons(seg) or extract_cons(body),
            "confidence": "확실"}


if __name__ == "__main__":
    import sys, json
    for path in sys.argv[1:]:
        t = open(path, encoding="utf-8", errors="replace").read()
        print(path, json.dumps(extract_qual(t), ensure_ascii=False))
