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
             "웨이파인딩", "사인", "안내체계", "안내표지", "표지판", "환경디자인", "디자인환경", "공공미술",
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
       "거리축제", "축제 운영", "축제운영", "행사대행", "행사 운영", "행사운영",
       # v2.1 (2026-07-28) — 필터 v2 정책("행사·축제·박람회 운영대행 제외")이 코드에서
       # 새고 있어 실측 노이즈가 39건 중 12건(31%)까지 올라온 것을 보정.
       # ① 해외 전시부스·수출관 시공 (우리 과업이 아니라 부스 시공·수출지원 사업)
       "박람회", "한국관", "산업전", "전시디자인설치공사", "전시 부스", "부스 디자인",
       # ② 운영대행·플랫폼 운영 (계획수립이 아니라 위탁 운영)
       "위탁운영", "플랫폼 운영",
       # ③ 교육과정 설계·컨설팅 (디자인 단과대학 공고가 WEAK 2개로 새어 들어옴)
       "교육과정"]
# === 조건부 제외 (2026-07-28, Andy 결정) =========================================
# 정책: 축제·행사의 **운영대행**은 뺀다. 그러나 축제·행사의 **경관·조명·공간 연출**은 남긴다.
# 이건 단어 하나로 못 가른다 — NEG에 "축제"나 "운영 용역"을 넣으면 시그마애드가 실제로
# 발표한 「2026 야간경관전시 조성·운영 용역」(울주문화재단)까지 같이 죽는다.
# 그래서 2단 조합으로 판정한다: 운영대행 성격어가 있어도, 우리가 실제 수행하는
# 연출·경관·조성 과업어가 함께 있으면 살린다.
OPS_COND  = ["축제", "행사", "운영 용역", "운영용역", "운영대행", "위탁 운영", "체험프로그램"]
CRAFT_KEEP = ["경관", "조명", "연출", "공간조성", "공간연출", "디자인", "설계", "조성",
              "가로환경", "사인", "안내체계", "색채"]

def is_ops_only(name):
    """운영대행 성격어만 있고 연출·경관·조성 과업어가 없으면 True(제외 대상)."""
    return any(k in name for k in OPS_COND) and not any(k in name for k in CRAFT_KEEP)

# === 공간유형 × 디자인의도 조합 채택 (v2.2 · 2026-07-30 신설) ====================
# 배경(실측): 부산광역시 공고 제2026-2348호
#   「공원·유원지 디자인환경 개선사업 설계용역」(기초 9억 · 마감 2026-08-28 · 공원여가정책과)
#   이 필터에서 통째로 누락됐다. 공고명에 STRONG이 0개였고("환경디자인"의 역순인
#   "디자인환경"만 있었다), WEAK는 "디자인" 1개뿐이라 2개 규칙에 걸리지 못했다.
#   입찰참가자격이 산업디자인전문회사(환경디자인 4442)라 명백히 우리 과업군이다.
#
# 규칙: 공공 공간유형어(SPACE) + 디자인/경관 의도어(DESIGN_INTENT)가 **함께** 있으면 STRONG 대우.
#   한쪽만으로는 절대 채택하지 않는다 — "○○공원 수목 전정"(공간만) 이나
#   "홍보물 디자인 제작"(의도만) 이 새어 들어오는 것을 막기 위함이다.
#   이 스캐너는 애초에 **용역 전용 엔드포인트**(…ServcPPSSrch)만 훑으므로
#   공사 공고는 구조적으로 유입되지 않는다. 조합 규칙을 안전하게 쓸 수 있는 이유다.
SPACE = ["공원", "유원지", "광장", "녹지", "수변", "하천", "둘레길", "산책로", "보행로",
         "전망대", "해수욕장", "해변", "포구", "어촌", "골목", "가로", "거리", "마을",
         "쉼터", "놀이터", "정원", "수목원", "캠핑장", "야영장", "공공공간", "지하도상가",
         "역세권", "터미널", "폐교", "유휴공간", "유휴부지", "옥상", "야외무대", "진입로"]
DESIGN_INTENT = ["디자인", "경관", "환경개선", "환경 개선", "개선사업", "연출", "특화",
                 "리뉴얼", "명소화", "정체성", "브랜딩", "이미지 개선", "공간조성", "공간구성"]

def space_design_hits(name):
    """공간유형어 + 디자인의도어가 함께 있으면 매칭어를 돌려준다(없으면 빈 리스트)."""
    s = [k for k in SPACE if k in name]
    d = [k for k in DESIGN_INTENT if k in name]
    return (s[:2] + d[:2]) if (s and d) else []

# --- 조건부 NEG (v2.2) ---------------------------------------------------------
# "실시설계·건축설계·구조설계"는 토목·건축 용역을 자르려고 넣은 단어인데,
# 경관·야간경관 과업은 실제로 「기본 및 실시설계」로 발주되는 경우가 많다.
# 실측 반례: "수변공원 야간경관 연출 기본 및 실시설계" — 우리 과업인데 통째로 죽었다.
# → STRONG 키워드가 함께 있으면 이 세 단어는 무시한다. 감리·측량은 우리 업역이 아니므로 유지.
NEG_SOFT = ["실시설계", "건축설계", "구조설계"]

# --- WEAK 2개 채택의 구조적 누수 차단 (v2.2 · H-24 잔여) ------------------------
# "KCC 농구단 디자인 및 인쇄 홍보물 제작"처럼 단순 인쇄물 제작이 WEAK 2개로 새어 들어왔다.
# 매칭된 WEAK가 아래 '인쇄물 제작' 집합 안에서만 나왔다면 채택하지 않는다.
# 「가이드라인 편집디자인」처럼 집합 밖 단어가 하나라도 섞이면 그대로 살린다.
PRINT_ONLY = {"디자인", "인쇄", "홍보물", "리플렛", "브로슈어", "굿즈"}

def is_print_only(weak_hits):
    return bool(weak_hits) and set(weak_hits).issubset(PRINT_ONLY)

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
        strong = [k for k in KW_STRONG if k in name]
        weak   = [k for k in KW_WEAK if k in name]
        sdhit  = space_design_hits(name)   # 공간유형 × 디자인의도 조합 (v2.2)
        # 부정키워드 — 하드는 무조건 제외, 소프트(설계 3종)는 STRONG 동반 시 통과
        if any(ng in name for ng in NEG if ng not in NEG_SOFT):
            continue
        if any(ng in name for ng in NEG_SOFT) and not strong:
            continue
        if is_ops_only(name):               # 운영대행 전용 건 제외(연출·경관 동반 시엔 통과)
            continue
        # 채택 규칙: STRONG 1개 이상 OR 공간×디자인 조합 OR WEAK 2개 이상
        if not (strong or sdhit or len(weak) >= 2):
            continue
        # WEAK 2개만으로 올라온 건이 '인쇄물 제작'뿐이면 제외 (H-24 잔여)
        if not strong and not sdhit and is_print_only(weak):
            continue
        # 기초금액 하한 컷 (금액 확인되고 하한 미만이면 제외, 미상은 통과시켜 눈으로 확인)
        raw_amt = it.get("presmptPrce") or it.get("asignBdgtAmt") or ""
        try:
            amt_val = int(raw_amt)
        except Exception:
            amt_val = 0
        if amt_val and amt_val < MIN_AMT:
            continue
        # 표시용 키워드: 중복 제거하되 등장 순서 유지
        hit_kw = list(dict.fromkeys(strong + sdhit + weak))
        tier = "S" if (strong or sdhit) else "W"
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
            "space": SPACE, "design_intent": DESIGN_INTENT,
        }, f, ensure_ascii=False)
    print(f"[저장] keywords.json (STRONG {len(KW_STRONG)} / WEAK {len(KW_WEAK)} / NEG {len(NEG)} "
          f"/ SPACE {len(SPACE)} × INTENT {len(DESIGN_INTENT)})")

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
