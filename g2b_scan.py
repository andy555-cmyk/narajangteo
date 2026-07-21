#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
나라장터 용역 입찰공고 자동 스캔 (SigmaAd PoC v2)
- 조달청_나라장터 입찰공고정보서비스 (data.go.kr/data/15129394)
- 최근 N일 용역 공고 전체 페이지네이션 → 키워드 필터 + 지역 태깅 → CSV 저장
사용법:  SERVICE_KEY=발급키  python3 g2b_scan.py
"""
import os, sys, json, csv, datetime, urllib.parse, requests
from g2b_rfp import rfp_status, attachments_of, get_rfp_text   # RFP 판별·첨부·본문추출
from g2b_spec import extract_spec                              # 제안서 작성기준(정성) 추출

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
             "디자인진흥", "공간디자인", "브랜드아이덴티티", "브랜드 아이덴티티", "슬로건", "정체성",
             # 도시재생 계열 (호진팀 도시기획·로컬브랜딩 과업군)
             "도시계획", "도시재생뉴딜", "우리동네살리기", "새뜰마을", "마을만들기", "마을가꾸기",
             "생활SOC", "지역재생", "소규모재생", "도시활력", "주민공동체", "빈집", "골목상권"]
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
       "체험학습", "현장체험학습", "숙박형", "수련활동", "키오스크", "배리어프리",
       "환경관리", "대기오염", "측정·분석", "측정분석", "수질", "소음", "악취", "자동측정", "오염물질",
       # 도시재생 계열 추가에 따른 노이즈 컷: 토목 도로·건설사업관리(CM) / 행사·축제 운영대행
       "도시계획도로", "건설사업관리", "통합건설", "사업관리용역", "감리용역",
       "거리축제", "축제 운영", "축제운영", "행사대행", "행사 운영", "행사운영"]
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
    att_map = {}          # 공고번호 → [[파일명, 다운로드URL], ...]
    rfp_items = {}        # 공고번호 → item (자동추출 공고만; 제안서 작성기준 추출용)
    seen_no = set()
    seen_name = set()
    for it in items:
        no = it.get("bidNtceNo", "")
        if no in seen_no:      # 공고번호 중복 제거(정정·차수 반복)
            continue
        seen_no.add(no)
        name = it.get("bidNtceNm", "") or ""
        nkey = name.strip()
        if nkey in seen_name:  # 동일 공고명 중복 제거(물품/용역 분리·재공고)
            continue
        seen_name.add(nkey)
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
        # 첨부 서류(과업지시서·제안요청서·공고문 등) 다운로드 링크 수집
        no_key = it.get("bidNtceNo", "")
        atts = [[n, u] for n, u in attachments_of(it) if u]
        if atts:
            att_map[no_key] = atts
        if rstat == "RFP_API":
            rfp_items[no_key] = it
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

    # 첨부 서류 다운로드 맵 저장 (대시보드 '서류' 팝업이 읽음)
    with open("attachments.json", "w", encoding="utf-8") as f:
        json.dump(att_map, f, ensure_ascii=False)
    print(f"[저장] attachments.json ({len(att_map)}건 첨부 보유)")

    # 검색 키워드 프로파일 저장 (대시보드에 '무엇으로 긁는지' 표시) — 단일 출처
    with open("keywords.json", "w", encoding="utf-8") as f:
        json.dump({
            "strong": KW_STRONG, "weak": KW_WEAK, "neg": NEG,
            "regions": REGIONS, "min_amt": MIN_AMT, "days_back": DAYS_BACK,
        }, f, ensure_ascii=False)
    print(f"[저장] keywords.json (STRONG {len(KW_STRONG)} / WEAK {len(KW_WEAK)} / NEG {len(NEG)})")

    # 제안서 작성기준(정성) 추출 → specs.json. 캐시: 이미 뽑은 공고는 재다운로드 안 함(공고번호 안정).
    try:
        specs = json.load(open("specs.json", encoding="utf-8"))
    except Exception:
        specs = {}
    keep_nos = {r["공고번호"] for r in rows}
    specs = {k: v for k, v in specs.items() if k in keep_nos}   # 사라진 공고 정리
    fetched = 0
    for no_key, it in rfp_items.items():
        if no_key in specs:            # 캐시 히트 → 스킵
            continue
        try:
            res = get_rfp_text(it, key)
            lines = extract_spec(res.get("text") or "")
            specs[no_key] = lines
            fetched += 1
        except Exception as e:
            specs[no_key] = []
    with open("specs.json", "w", encoding="utf-8") as f:
        json.dump(specs, f, ensure_ascii=False)
    print(f"[저장] specs.json (제안서 작성기준 {sum(1 for v in specs.values() if v)}건 · 신규추출 {fetched})")

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
