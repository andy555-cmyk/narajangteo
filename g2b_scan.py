#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
나라장터 용역 입찰공고 자동 스캔 (SigmaAd PoC v2)
- 조달청_나라장터 입찰공고정보서비스 (data.go.kr/data/15129394)
- 최근 N일 용역 공고 전체 페이지네이션 → 키워드 필터 + 지역 태깅 → CSV 저장
사용법:  SERVICE_KEY=발급키  python3 g2b_scan.py
"""
import os, sys, json, csv, datetime, urllib.parse, requests
from g2b_rfp import rfp_status   # 제안요청서 API 포함 여부 판별

RFP_LABEL = {"RFP_API": "자동추출", "NOTICE_ONLY": "규격서별도", "NONE": "첨부없음"}

BASE = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServcPPSSrch"

# === 이승원(시그마애드/호진팀) 실제 과업 성격 기반 프로파일 ===
# 근거 과업: 태종대 서비스디자인/웨이파인딩, 울산·포항 공공가이드라인, 부산 디자인클러스터,
#          남해군 경관가이드라인, 고속도로 공공디자인, 기장 WDC 디자인클러스터, 창원 국가산단 경관 등
# → 핵심 도메인: 공공디자인 · 경관 · 유니버설/서비스디자인 · 도시브랜딩 · 디자인 클러스터/진흥

# STRONG: 하나만 걸려도 우리 과업일 가능성 매우 높음
KW_STRONG = ["공공디자인", "경관", "유니버설디자인", "유니버설 디자인", "서비스디자인", "서비스 디자인",
             "웨이파인딩", "사인", "안내체계", "안내표지", "표지판", "환경디자인", "공공미술",
             "도시브랜딩", "도시브랜드", "도시디자인", "도시재생", "색채", "야간경관", "경관계획",
             "가로환경", "가로경관", "디자인클러스터", "디자인 클러스터", "디자인혁신", "디자인 혁신",
             "디자인진흥", "공간디자인", "브랜드아이덴티티", "브랜드 아이덴티티", "슬로건", "정체성"]
# ※ "BI" 2글자 토큰은 BIS/BIM/BIO/BIPV 오탐 → 제거. 필요시 "경관BI","공식BI" 등 맥락형으로만.
# WEAK: 2개 이상 겹치면 채택 (행사·축제·관광·계획수립류는 노이즈라 제외 — 행사 X 결정)
KW_WEAK = ["디자인", "브랜딩", "브랜드", "가이드라인", "매뉴얼", "편집디자인", "굿즈", "캐릭터",
           "콘텐츠", "전시", "체험", "인쇄", "홍보물", "리플렛", "브로슈어", "활성화"]

REGIONS = ["부산", "경남", "경상남", "경북", "경상북", "울산", "창원", "김해", "양산", "진주",
           "포항", "구미", "안동", "남해", "거제", "통영", "기장"]
# 부정키워드: 공고명에 있으면 제외 (건축설계·토목·시설유지 등 비디자인 용역)
NEG = ["임대", "렌탈", "리스", "유지보수", "유지관리", "수학여행", "수련", "급식",
       "CT", "MRI", "진단", "의료", "병원", "환자", "약품", "시약",
       "청소", "경비", "방역", "소독", "수목", "제초", "보험", "실시설계", "건축설계",
       "구조설계", "감리", "측량", "전기공사", "통신공사", "관급", "차량", "연료", "냉난방",
       "소프트웨어", "시스템 유지", "정보화", "전산", "임차", "물품구매",
       "철거", "폐기물", "정산 용역", "굴착", "포장공사",
       "체험학습", "현장체험학습", "숙박형", "수련활동", "키오스크", "배리어프리"]
MIN_AMT   = 50_000_000   # 기초금액 하한 (5천만원)
# 게시일 최근 30일을 훑고 '진행중(마감 미도래)'만 남김 → 좋은 공고가 시간 지나도
# 마감 전까지 안 사라짐(스크롤 오프 방지). 접수기간이 보통 30일 이내라 사실상 열린 공고 전부 포착.
DAYS_BACK = 30
PER_PAGE  = 999

def fetch_all(key):
    end = datetime.datetime.now()
    start = end - datetime.timedelta(days=DAYS_BACK)
    common = {
        "serviceKey": key, "inqryDiv": "1",
        "inqryBgnDt": start.strftime("%Y%m%d") + "0000",
        "inqryEndDt": end.strftime("%Y%m%d") + "2359",
        "type": "json", "numOfRows": str(PER_PAGE),
    }
    allitems, page, total = [], 1, None
    while True:
        p = dict(common, pageNo=str(page))
        r = requests.get(BASE + "?" + urllib.parse.urlencode(p), timeout=30)
        d = json.loads(r.text)
        body = d.get("response", {}).get("body", {})
        total = body.get("totalCount", 0)
        items = body.get("items", [])
        if isinstance(items, dict):
            items = items.get("item", [])
        if not items:
            break
        allitems.extend(items)
        if len(allitems) >= total or page > 60:
            break
        page += 1
    return allitems, total, common

def main():
    key = os.environ.get("SERVICE_KEY", "").strip()
    if not key:
        print("!! SERVICE_KEY 비어있음"); sys.exit(1)
    items, total, common = fetch_all(key)
    today = datetime.datetime.now()
    print(f"기간 {common['inqryBgnDt']}~{common['inqryEndDt']}")
    print(f"전체 용역공고 {total}건 · 실제 수신 {len(items)}건\n")

    rows = []
    seen_no = set()
    for it in items:
        no = it.get("bidNtceNo", "")
        if no in seen_no:      # 공고번호 중복 제거(정정·차수 반복)
            continue
        seen_no.add(no)
        name = it.get("bidNtceNm", "") or ""
        org  = (it.get("dminsttNm", "") or "") + " " + (it.get("ntceInsttNm", "") or "")
        region_fld = it.get("prtcptPsblRgnNm", "") or ""
        if any(ng in name for ng in NEG):   # 부정키워드 우선 제외
            continue
        strong = [k for k in KW_STRONG if k in name]
        weak   = [k for k in KW_WEAK if k in name]
        # 채택 규칙: STRONG 1개 이상 OR WEAK 2개 이상
        if not (strong or len(weak) >= 2):
            continue
        # 기초금액 하한 컷 (금액 확인되고 하한 미만이면 제외, 미상은 통과시켜 눈으로 확인)
        raw_amt = it.get("presmptPrce") or it.get("asignBdgtAmt") or ""
        try:
            amt_val = int(raw_amt)
        except Exception:
            amt_val = 0
        if amt_val and amt_val < MIN_AMT:
            continue
        hit_kw = strong + weak
        tier = "S" if strong else "W"
        blob = f"{name} {org} {region_fld}"
        is_region = any(rg in blob for rg in REGIONS)
        # 마감 여부
        clse = it.get("bidClseDt", "") or ""
        alive = True
        try:
            alive = datetime.datetime.strptime(clse[:16], "%Y-%m-%d %H:%M") >= today
        except Exception:
            pass  # 마감일 미상은 진행중으로 간주(방문접수 등)
        if not alive:
            continue  # 마감 지난 공고는 대시보드에서 자동 제외
        rstat, _, _ = rfp_status(it)
        rows.append({
            "등급": tier,
            "RFP": RFP_LABEL.get(rstat, rstat),
            "지역매칭": "Y" if is_region else "",
            "진행중": "Y" if alive else "마감",
            "공고명": name.strip(),
            "수요기관": (it.get("dminsttNm") or "").strip(),
            "기초금액": it.get("presmptPrce") or it.get("asignBdgtAmt") or "",
            "참가지역": region_fld or "제한없음",
            "마감": clse,
            "키워드": ",".join(hit_kw),
            "공고번호": it.get("bidNtceNo", ""),
            "상세": it.get("bidNtceDtlUrl") or it.get("bidNtceUrl") or "",
        })

    # 정렬: 지역매칭 우선 → 진행중 우선 → 기초금액 큰 순
    def amt(r):
        try: return int(r["기초금액"])
        except: return 0
    rows.sort(key=lambda r: (r["등급"] != "S", r["지역매칭"] != "Y", r["진행중"] != "Y", -amt(r)))

    nS = sum(1 for r in rows if r["등급"] == "S")
    region_alive = [r for r in rows if r["등급"] == "S" and r["지역매칭"] == "Y" and r["진행중"] == "Y"]
    print(f"== 채택 총 {len(rows)}건 (STRONG {nS} / WEAK {len(rows)-nS}) "
          f"| 지역 {sum(1 for r in rows if r['지역매칭']=='Y')} | 진행중 {sum(1 for r in rows if r['진행중']=='Y')} ==\n")
    print(f"◆ 최우선 타깃 (STRONG+지역+진행중) {len(region_alive)}건\n")
    for r in region_alive:
        amt_str = f"{amt(r):,}" if amt(r) else "-"
        print(f"• [{r['등급']}·RFP:{r['RFP']}] {r['공고명']}")
        print(f"   {r['수요기관']} | 기초 {amt_str}원 | 마감 {r['마감']}")
        print(f"   키워드[{r['키워드']}] | {r['상세']}\n")

    # RFP 상태 분포 요약
    from collections import Counter
    dist = Counter(r["RFP"] for r in rows)
    print("── RFP 확보경로 분포:", dict(dist),
          "(자동추출=API로 제안요청서 확보 / 규격서별도=브라우저 / 첨부없음=방문·전화) ──\n")

    with open("g2b_result.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["없음"])
        w.writeheader(); w.writerows(rows)
    print(f"[저장] g2b_result.csv ({len(rows)}건)")

    # 대시보드 자동 생성
    try:
        import subprocess
        bgn, end = common["inqryBgnDt"][:8], common["inqryEndDt"][:8]
        period = f"{bgn[:4]}-{bgn[4:6]}-{bgn[6:]} ~ {end[4:6]}-{end[6:]}"
        gen = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        subprocess.run([sys.executable, "build_dashboard.py", str(total), period, gen], check=True)
    except Exception as e:
        print("[대시보드 생성 건너뜀]", e)

if __name__ == "__main__":
    main()
