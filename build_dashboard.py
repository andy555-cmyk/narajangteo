#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_dashboard.py — g2b_result.csv → 자립형 HTML 대시보드(g2b_dashboard.html)
스타일: Finexy 레퍼런스 기반 — 웜 오프화이트 캔버스, 라운드 bento 카드, 코랄 액센트 1개,
        상태 컬러 점(●), 표 카드 우상단 검색/필터. (SigmaAd 기준: 저채도 액센트·모노 숫자·헤어라인)
사용: python3 build_dashboard.py [전체스캔건수] [기간문자열] [생성시각]
"""
import csv, json, sys, re

RAW_TOTAL = sys.argv[1] if len(sys.argv) > 1 else "?"
PERIOD    = sys.argv[2] if len(sys.argv) > 2 else ""
GEN_AT    = sys.argv[3] if len(sys.argv) > 3 else ""

def won_fmt(v):
    try: n = int(v)
    except: return "미상"
    if n >= 100000000: return f"{n/100000000:.1f}억"
    if n >= 10000: return f"{n//10000:,}만"
    return f"{n:,}"

import datetime as _dt

# D-day 기준일. 배치가 넘겨주는 생성시각(GEN_AT)을 우선 쓴다 — 같은 입력이면 같은 HTML이
# 나와야 재실행·재현이 가능하기 때문. GEN_AT이 없을 때만 오늘 날짜로 폴백한다.
# ⚠ 과거에 이 값이 date(2026,7,18)로 하드코딩돼 있어 7/19부터 매일 하루씩 어긋났다.
#   (2026-07-28 기준 전 건 D-day가 +10일 부풀려져 '마감임박' 표시가 0건으로 죽어 있었음)
def _base_date():
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", GEN_AT or "")
    if m:
        try: return _dt.date(*map(int, m.groups()))
        except ValueError: pass
    return _dt.date.today()

BASE_DATE = _base_date()

def dday(clse):
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", clse or "")
    if not m: return None
    try: d = _dt.date(*map(int, m.groups()))
    except ValueError: return None
    return (d - BASE_DATE).days

import glob as _glob
have_report = set(re.findall(r"report_([A-Za-z0-9]+)\.html", " ".join(_glob.glob("report_*.html"))))

# 판정(적극/조건부/보류) — 분석 JSON에서 join
verdicts = {}
for jf in _glob.glob("reports_data/R26BK*.json"):
    try:
        jd = json.load(open(jf, encoding="utf-8"))
        verdicts[jd.get("no", "")] = (jd.get("fit") or {}).get("verdict", "")
    except Exception:
        pass
VRANK = {"적극 검토": 0, "조건부 검토": 1, "보류": 2, "": 3}

# 첨부 서류(과업지시서·제안요청서·공고문) 다운로드 맵
try:
    ATT = json.load(open("attachments.json", encoding="utf-8"))
except Exception:
    ATT = {}

# 검색 키워드 프로파일 (대시보드에 '무엇으로 긁는지' 표시)
try:
    KWP = json.load(open("keywords.json", encoding="utf-8"))
except Exception:
    KWP = {"strong": [], "weak": [], "neg": [], "regions": [], "min_amt": 0, "days_back": 0}

# 제안서 작성기준(정성) — 공고번호 → [규격·유의사항 줄...]
try:
    SPECS = json.load(open("specs.json", encoding="utf-8"))
except Exception:
    SPECS = {}

# 데이터 공백 보충 (v2.6) — `data_fill.json`
# 배경: 일일 배치 봇이 만든 specs.json·attachments.json 은 그 시점 필터로 잡힌 공고만 담는다.
#   필터를 넓히면(v2.2) 새로 잡힌 공고는 base 데이터에 항목이 없어 「작성기준·서류」 버튼이 사라진다.
#   실측 2026-07-30: 43건 중 13건이 공백이었고 그중 3건이 '적극 검토' 건이었다.
# 규칙: **base 가 항상 우선.** 이 파일은 base 에 없는 키만 채운다.
#   따라서 다음 배치가 base 를 재생성하면 이 파일은 자동으로 무효화된다(덮어쓰지 않는다).
try:
    _FILL = json.load(open("data_fill.json", encoding="utf-8"))
    for _k, _v in (_FILL.get("specs") or {}).items():
        SPECS.setdefault(_k, _v)
    for _k, _v in (_FILL.get("attachments") or {}).items():
        ATT.setdefault(_k, _v)
except Exception:
    _FILL = {}

# 참가자격 태그 (v2.4) — 공고번호 → {req:[태그], region_limit, consortium, confidence}
# ⚠ 이건 '채택 조건'이 아니다. 수집은 자격과 무관하게 넓게 한다(2026-07-30 대표 결정).
#   여기 값은 대표가 화면에서 보유 자격을 체크했을 때 **표시·필터**에만 쓴다.
try:
    _Q = json.load(open("qualifications.json", encoding="utf-8"))
    QUAL_TAGS = _Q.get("tags", {})
    _CUR = _Q.get("curated", _Q.get("items", {}))    # 사람·LLM 검수본 (우선)
    _AUTO = _Q.get("auto", {})                        # 배치 규칙 기반 자동판독
except Exception:
    QUAL_TAGS, _CUR, _AUTO = {}, {}, {}

def qual_of(no):
    """검수본이 있으면 그것을, 없으면 자동판독을 쓴다. 출처를 src로 알려준다."""
    if no in _CUR:
        return dict(_CUR[no], src="검수")
    if no in _AUTO:
        return dict(_AUTO[no], src="자동")
    return {"req": [], "region_limit": "", "consortium": "", "confidence": "불확실", "src": "없음"}
HOME_REGION = "부산광역시"   # 자사 본점 소재지 — 지역제한 판정 기준

# 제안서 착수 결정 — 공고번호 → {status:"진행", figma:"url", started:"date"}
try:
    DECIDE = json.load(open("decisions.json", encoding="utf-8"))
except Exception:
    DECIDE = {}

# 참가지역 제한 게이트 판별용(우리 활동권)
REGIONS_D = ["부산", "경남", "경상남", "경북", "경상북", "울산", "창원", "김해", "양산", "진주",
             "포항", "구미", "안동", "남해", "거제", "통영", "기장"]

rows = list(csv.DictReader(open("g2b_result.csv", encoding="utf-8-sig")))
data = []
for r in rows:
    try: amt = int(r["기초금액"])
    except: amt = 0
    no = r["공고번호"]
    pr = (r.get("참가지역") or "").strip()
    limited = bool(pr) and ("제한없음" not in pr) and ("전국" not in pr)
    ours = any(rg in pr for rg in REGIONS_D)
    region_gate = "block" if (limited and not ours) else ("ok" if (limited and ours) else "")
    _q = qual_of(no)
    data.append({
        "grade": r["등급"], "rfp": r["RFP"], "region": r["지역매칭"] == "Y",
        "name": r["공고명"], "org": r["수요기관"], "amt": amt, "amtLabel": won_fmt(r["기초금액"]),
        "clse": (r["마감"] or "").strip(), "dday": dday(r["마감"]),
        "kw": r["키워드"], "no": no, "url": r["상세"],
        "report": f"report_{no}.html" if no in have_report else "",
        "verdict": verdicts.get(no, ""),
        "docs": ATT.get(no, []),
        "prtcpt": pr, "gate": region_gate,
        "spec": SPECS.get(no, []),
        "decided": DECIDE.get(no) or {},
        "req": _q["req"], "regLimit": _q["region_limit"],
        "cons": _q["consortium"], "qconf": _q["confidence"], "qsrc": _q["src"],
    })
# === 자동 1차 분류 (v2.2 · 2026-07-30) =========================================
# ⚠ 이것은 '판정'이 아니다. 사람이 쓴 과업분석 리포트(reports_data/*.json)의 판정만이 판정이다.
#   자동 분류는 리포트를 아직 못 쓴 공고를 **어떤 순서로 손댈지** 정하기 위한 기계적 줄세우기다.
#   화면에서도 '자동' 뱃지를 붙여 사람 판정과 절대 섞이지 않게 표시한다.
# 배경: 채택 목록은 매일 자동으로 갈리는데 리포트는 수동이라 미분석이 계속 쌓인다
#   (2026-07-30 실측 36건 중 28건 미분석). 미분석 28건이 전부 같은 회색 덩어리로 보이면
#   무엇부터 열어야 할지 알 수 없다. 그것이 이 분류의 유일한 목적이다.
AUTO_RANK = {"A": 0, "B": 1, "C": 2}

def auto_class(d):
    """규칙 기반 1차 분류. (등급, 점수, 근거리스트) — 추정·예측이 아니라 필드값의 합산이다."""
    sc, why = 0, []
    if d["grade"] == "S":
        sc += 2; why.append("STRONG 매칭")
    if d["region"]:
        sc += 2; why.append("부·울·경")
    if d["rfp"] == "자동추출":
        sc += 1; why.append("RFP 자동추출")
    if d["amt"] >= 300_000_000:
        sc += 2; why.append("기초 3억↑")
    elif d["amt"] >= 100_000_000:
        sc += 1; why.append("기초 1억↑")
    dd = d["dday"]
    if dd is not None and 0 <= dd <= 2:
        sc -= 2; why.append("마감 D-2 이내(착수 난이)")
    elif dd is not None and dd >= 10:
        sc += 1; why.append("준비기간 10일↑")
    if d["gate"] == "block":
        sc -= 5; why.append("타지역 전용 참가제한")
    g = "A" if sc >= 6 else ("B" if sc >= 3 else "C")
    return g, sc, why

for d in data:
    d["auto"], d["autoScore"], d["autoWhy"] = auto_class(d)

# 판정 우선 → (미분석은 자동분류 우선) → 금액순. 붙을 것부터 위로.
data.sort(key=lambda x: (VRANK.get(x["verdict"], 3), AUTO_RANK.get(x["auto"], 3), -x["amt"]))

# 신규(NEW) 추적: store.json에 공고 첫 등장일 기록 → 오늘 처음 뜬 공고 표시
import os
TODAY = (GEN_AT or "")[:10]
store_existed = os.path.exists("store.json")
try:
    store = json.load(open("store.json", encoding="utf-8")) if store_existed else {}
except Exception:
    store = {}
# 이전 실행에 '오늘보다 과거' 기록이 있어야 NEW 판정 시작 → seed일(전부 오늘) & 같은날 재실행엔 NEW 없음
has_history = any(v < TODAY for v in store.values())
new_store = {}
for d in data:
    fs = store.get(d["no"], TODAY)   # 처음 보는 공고면 오늘로 기록
    new_store[d["no"]] = fs
    d["isNew"] = bool(has_history and fs == TODAY)
json.dump(new_store, open("store.json", "w", encoding="utf-8"), ensure_ascii=False)

nGo = sum(1 for d in data if d["verdict"] == "적극 검토")
nCond = sum(1 for d in data if d["verdict"] == "조건부 검토")
# 미분석 = 개별 과업분석 리포트(reports_data/*.json)가 아직 없는 공고.
# 공고 목록은 매일 자동으로 갈리는데 리포트는 수동 작성이라 반드시 밀린다.
# 이 숫자를 감추면 상단 KPI가 '검토 결과'가 아니라 '작업 적체량'을 조용히 대신 표시하게 된다.
nNA = sum(1 for d in data if not d["verdict"])
# 미분석 안에서 자동 1차 분류가 A인 건 = "리포트를 오늘 안에 써야 할 후보"
nNAA = sum(1 for d in data if not d["verdict"] and d["auto"] == "A")
nNAB = sum(1 for d in data if not d["verdict"] and d["auto"] == "B")
nNear = sum(1 for d in data if d["dday"] is not None and 0 <= d["dday"] <= 7)
nNew = sum(1 for d in data if d["isNew"])
nS = sum(1 for d in data if d["grade"] == "S")
nAuto = sum(1 for d in data if d["rfp"] == "자동추출")
nRegion = sum(1 for d in data if d["region"])
maxAmt = won_fmt(max((d["amt"] for d in data), default=0))

# 분석용 분포(실데이터)
from collections import Counter
kwc = Counter()
for d in data:
    for k in (d["kw"] or "").split(","):
        k = k.strip()
        if k: kwc[k] += 1
kw_top = kwc.most_common(8)
kw_max = kw_top[0][1] if kw_top else 1
KW_STAT = [{"label": k, "n": v, "pct": round(v / len(data) * 100)} for k, v in kw_top]

rfp_order = [("자동추출", "gn"), ("규격서별도", "am"), ("첨부없음", "rd")]
rc = Counter(d["rfp"] for d in data)
RFP_STAT = [{"label": l, "n": rc.get(l, 0), "pct": round(rc.get(l, 0) / len(data) * 100), "c": c}
            for l, c in rfp_order]

HTML = r"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>나라장터 공고 스캔 대시보드</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>
<!-- 본문은 Pretendard 하나로 간다. Noto Sans KR(한글 5웨이트)을 같이 받고 있었으나
     font-family 우선순위상 Pretendard가 항상 이겨서 한 번도 그려지지 않는 사(死)폰트였다.
     한글 웹폰트는 용량이 커서 폰에서 특히 손해 → 제거. 폴백은 OS 기본 한글 서체가 받는다.
     숫자는 .mono(IBM Plex Mono)가 계속 쓰므로 그것만 남긴다. -->
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">
<style>
:root{
 --canvas:#F1EFEB; --card:#FFFFFF; --ink:#1A1A1A; --ink2:#3A3A38; --muted:#8C8C86;
 --line:#ECEAE5; --accent:#E9663A; --accent-2:#F2916B; --accent-soft:#FCEEE7;
 --gn:#2E9E5B; --gn-bg:#E9F6EF; --am:#C6871F; --am-bg:#FBF1DC; --rd:#D6493C; --rd-bg:#FBE7E4;
 --bl:#2B7BB0; --bl-bg:#E6F1FA;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--canvas);color:var(--ink);
 font-family:'Pretendard',-apple-system,'Apple SD Gothic Neo','Malgun Gothic','Noto Sans KR',sans-serif;
 line-height:1.6;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;padding:34px 26px 60px}
.wrap{max-width:1320px;margin:0 auto}
.mono{font-variant-numeric:tabular-nums;font-family:'IBM Plex Mono','SF Mono',ui-monospace,Menlo,Consolas,monospace;letter-spacing:-.01em}

/* 헤더 */
.eyebrow{font-size:12.5px;font-weight:600;letter-spacing:.18em;text-transform:uppercase;color:var(--accent)}
h1{font-size:32px;font-weight:800;letter-spacing:-.035em;line-height:1.12;margin:7px 0 7px;color:var(--ink)}
.sub{color:var(--muted);font-size:15px}
.sub b{color:var(--ink2);font-weight:600}

/* KPI bento */
.kpis{display:grid;grid-template-columns:1.35fr 1fr 1fr 1fr 1fr;gap:14px;margin:26px 0 20px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:20px 22px;
 box-shadow:0 1px 2px rgba(0,0,0,.03),0 10px 26px -16px rgba(0,0,0,.14);position:relative;min-height:120px;
 display:flex;flex-direction:column;justify-content:space-between}
.kpi.hero{background:linear-gradient(135deg,var(--accent) 0%,var(--accent-2) 100%);border:0;color:#fff}
.kpi .top{display:flex;justify-content:space-between;align-items:flex-start}
.kpi .l{font-size:14px;color:var(--muted);font-weight:500}
.kpi.hero .l{color:rgba(255,255,255,.9)}
.kpi .ic{width:33px;height:33px;border-radius:9px;background:#F6F4F0;display:flex;align-items:center;justify-content:center}
.kpi.hero .ic{background:rgba(255,255,255,.2)}
.kpi .ic svg{width:18px;height:18px;stroke:var(--muted);fill:none;stroke-width:1.7}
.kpi.hero .ic svg{stroke:#fff}
.kpi .n{font-size:34px;font-weight:800;letter-spacing:-.03em;line-height:1}
.kpi .cap{font-size:13px;color:var(--muted);margin-top:5px}
.kpi.hero .cap{color:rgba(255,255,255,.85)}

/* 분석(가로 막대) */
.analytics{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:20px}
.acard{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:20px 22px;
 box-shadow:0 1px 2px rgba(0,0,0,.03),0 10px 26px -16px rgba(0,0,0,.14)}
.acard h3{font-size:15px;font-weight:700;letter-spacing:-.01em;margin-bottom:16px}
.acard h3 .c{color:var(--muted);font-weight:500;font-size:13.5px;margin-left:5px}
.brow{display:grid;grid-template-columns:96px 1fr 40px;align-items:center;gap:10px;margin:9px 0}
.brow .bl{font-size:13.5px;color:var(--ink2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.btrack{height:9px;background:#F1EFEB;border-radius:6px;overflow:hidden}
.bfill{height:100%;border-radius:6px;background:linear-gradient(90deg,var(--accent),var(--accent-2))}
.bfill.gn{background:var(--gn)} .bfill.am{background:var(--am)} .bfill.rd{background:var(--rd)}
.brow .bn{font-size:13.5px;font-weight:700;text-align:right;color:var(--ink2)}
@media(max-width:860px){.analytics{grid-template-columns:1fr}}

/* 테이블 카드 */
.panel{background:var(--card);border:1px solid var(--line);border-radius:20px;padding:8px 8px 8px;
 box-shadow:0 1px 2px rgba(0,0,0,.03),0 14px 34px -20px rgba(0,0,0,.16)}
.phead{display:flex;justify-content:space-between;align-items:center;gap:14px;padding:16px 16px 12px;flex-wrap:wrap}
.ptitle{font-size:17.5px;font-weight:700;letter-spacing:-.02em}
.ptitle .c{color:var(--muted);font-weight:500;font-size:14.5px;margin-left:6px}
.tools{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.search{position:relative}
.search input{width:236px;max-width:48vw;padding:8px 13px 8px 32px;border:1px solid var(--line);border-radius:22px;
 font-size:14.5px;font-family:inherit;background:#FAF9F7;color:var(--ink)}
.search input:focus{outline:none;border-color:var(--accent);background:#fff}
.search svg{position:absolute;left:11px;top:11px;width:15px;height:15px;stroke:var(--muted);fill:none;stroke-width:1.8}

/* 필터 바 — 축(그룹)별로 세그먼트를 나눠 눈이 끊기게 한다.
   평면 나열은 6개 축이 한 덩어리로 보여 무엇이 무엇의 선택지인지 읽히지 않았다. */
.fbar{display:flex;flex-wrap:wrap;gap:14px 20px;padding:2px 16px 16px;align-items:flex-end}
.fgrp{display:flex;flex-direction:column;gap:6px}
.flab{font-size:11.5px;font-weight:700;letter-spacing:.14em;color:var(--muted);padding-left:2px}
.seg{display:inline-flex;background:var(--soft);border:1px solid var(--line);border-radius:11px;padding:3px;gap:2px}
.seg .chip{padding:6px 12px;border:0;border-radius:8px;background:transparent;font-size:13.5px;
 font-weight:600;color:var(--muted);box-shadow:none}
.seg .chip:hover{color:var(--ink2);background:rgba(0,0,0,.03)}
.seg .chip.on{background:#fff;color:var(--ink);font-weight:700;
 box-shadow:0 0 0 1px rgba(0,0,0,.05),0 1px 2px -.5px rgba(0,0,0,.06),0 3px 3px -1.5px rgba(0,0,0,.04)}
.chips{display:flex;gap:6px;align-items:center;flex-wrap:wrap;padding:0 16px 12px}
.chips .lab{font-size:12.5px;color:var(--muted);margin:0 3px}
.chip{padding:6px 12px;border:1px solid var(--line);border-radius:20px;background:#fff;
 font-size:14px;color:var(--ink2);cursor:pointer;transition:.12s}
.chip:hover{border-color:var(--accent-2)}
.chip.on{background:var(--ink);border-color:var(--ink);color:#fff;font-weight:600}

table{width:100%;border-collapse:collapse;font-size:14.5px}
thead th{text-align:left;padding:11px 16px;font-size:12.5px;font-weight:600;letter-spacing:.03em;
 text-transform:uppercase;color:var(--muted);border-top:1px solid var(--line);border-bottom:1px solid var(--line);
 background:#FAF9F7;white-space:nowrap}
thead th.sortable{cursor:pointer;user-select:none}
thead th.sortable:hover{color:var(--accent)}
thead th .ar{opacity:.55;font-size:11px;margin-left:2px}
tbody td{padding:17px 16px;border-bottom:1px solid var(--line);vertical-align:top}
tbody td:first-child{width:142px}
/* 판정 셀의 뱃지는 세로로 쌓는다 — 옆으로 붙으면 판정과 자격이 한 덩어리로 읽힌다 */
tbody td:first-child .vb,tbody td:first-child .autob,tbody td:first-child .qb{display:flex;width:fit-content}
/* 숫자·날짜·지역 열은 절대 줄바꿈하지 않는다 (08-\n10, 부\n울\n경 깨짐 방지) */
tbody td:nth-child(3),tbody td:nth-child(4),tbody td:nth-child(5),tbody td:nth-child(6){
 white-space:nowrap;vertical-align:middle}
tbody td:nth-child(4){width:92px}
tbody td:nth-child(6){width:78px}
tbody td:last-child{min-width:152px;max-width:230px}
tbody tr:last-child td{border-bottom:0}
tbody tr:hover{background:#FBFAF8}
.name{font-weight:600;color:var(--ink);text-decoration:none;letter-spacing:-.01em;font-size:15px}
.name:hover{color:var(--accent);text-decoration:underline}
.org{color:var(--muted);font-size:13px;margin-top:3px}
.name{cursor:default}
/* 행 액션 — 솔리드는 '과업분석 보고서' 하나만. 나머지는 아웃라인·아이콘으로 내린다.
   같은 무게의 버튼 5개가 나열되면 무엇부터 눌러야 하는지 알 수 없다. */
.rlinks{margin-top:9px;display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.rsep{width:1px;height:20px;background:var(--line);margin:0 3px}
.ibtn{width:32px;height:32px;display:inline-flex;align-items:center;justify-content:center;
 border:1px solid var(--line);border-radius:9px;background:#fff;cursor:pointer;padding:0;
 position:relative;transition:.12s;color:var(--muted);text-decoration:none}
.ibtn:hover{border-color:var(--ink2);color:var(--ink)}
.ibtn svg{width:17px;height:17px;fill:none;stroke:currentColor;stroke-width:1.7;
 stroke-linecap:round;stroke-linejoin:round}
.ibtn .num{position:absolute;top:-7px;right:-7px;box-shadow:0 0 0 2px #fff;min-width:17px;height:17px;line-height:17px;
 padding:0 3px;border-radius:8px;background:var(--ink);color:#fff;font-size:11.5px;font-weight:700;
 text-align:center;font-variant-numeric:tabular-nums}
.btn-report{font-family:inherit;font-size:13.5px;font-weight:700;color:#fff;background:var(--accent);border:0;padding:6px 14px;border-radius:9px;cursor:pointer;transition:.12s;
 box-shadow:0 1px 2px -.5px rgba(0,0,0,.10),0 3px 3px -1.5px rgba(0,0,0,.06)}
.btn-report:hover{filter:brightness(.94)}
.btn-g2b{font-size:13.5px;font-weight:600;color:var(--ink2);text-decoration:none;background:#fff;border:1px solid var(--line);padding:6px 12px;border-radius:8px}
.btn-g2b:hover{border-color:var(--accent);color:var(--accent)}
.btn-wait{font-size:13.5px;font-weight:600;color:var(--muted);background:#F1EFEB;padding:6px 12px;border-radius:8px}
.btn-doc{font-family:inherit;font-size:13.5px;font-weight:600;color:var(--bl);background:var(--bl-bg);border:1px solid #CBE0F0;padding:6px 12px;border-radius:8px;cursor:pointer}
.btn-doc:hover{filter:brightness(.97)}
.btn-spec{font-family:inherit;font-size:13.5px;font-weight:600;color:#7A5AA6;background:#F1ECF8;border:1px solid #DED0F0;padding:6px 12px;border-radius:8px;cursor:pointer}
.btn-spec:hover{filter:brightness(.97)}
/* 제안서 착수 버튼 + 진행중 상태 */
.btn-start{font-family:inherit;font-size:13.5px;font-weight:700;color:var(--ink2);background:#fff;
 border:1px solid var(--line);padding:6px 13px;border-radius:9px;cursor:pointer;transition:.12s}
.btn-start:hover{border-color:var(--ink);color:var(--ink)}
.btn-live{display:inline-flex;align-items:center;gap:6px;font-size:13.5px;font-weight:800;color:var(--gn);background:var(--gn-bg);border:1px solid #BDE5CD;padding:6px 12px;border-radius:8px}
.btn-live .ld{width:8px;height:8px;border-radius:50%;background:var(--gn);animation:newpulse 1.8s ease-in-out infinite}
.btn-figma{font-size:13.5px;font-weight:700;color:var(--ink2);background:#fff;border:1px solid var(--line);text-decoration:none;padding:6px 12px;border-radius:9px;display:inline-flex;align-items:center;gap:5px}
.btn-figma:hover{background:var(--accent)}
/* 착수 모달 */
.startbox{padding:22px 24px 24px;overflow-y:auto;max-height:calc(92vh - 46px)}
.startbox h4{font-size:17.5px;font-weight:800;color:var(--ink);margin-bottom:4px}
.startbox .sub{font-size:14px;color:var(--muted);margin-bottom:16px;line-height:1.5}
.pipeline{display:flex;gap:8px;margin:14px 0 18px;flex-wrap:wrap}
.pstep{flex:1;min-width:120px;background:var(--soft);border:1px solid var(--line);border-radius:10px;padding:11px 13px}
.pstep .pn{font-size:11.5px;font-weight:800;color:var(--accent);letter-spacing:.04em}
.pstep .pt{font-size:14px;font-weight:700;color:var(--ink);margin-top:3px}
.pstep .pd{font-size:12.5px;color:var(--muted);margin-top:2px;line-height:1.4}
.cmdbox{background:#1A1A1A;color:#EDE9E2;border-radius:10px;padding:14px 16px;font-size:14px;line-height:1.6;white-space:pre-wrap;font-family:ui-monospace,monospace;margin-top:4px}
.copyrow{display:flex;gap:10px;align-items:center;margin-top:12px;flex-wrap:wrap}
.btn-copy{font-family:inherit;font-size:14.5px;font-weight:800;color:#fff;background:var(--accent);border:0;padding:10px 18px;border-radius:9px;cursor:pointer}
.btn-copy:hover{filter:brightness(.95)}
.copyhint{font-size:13px;color:var(--muted)}
.startnote{font-size:13.5px;color:var(--ink2);background:var(--accent-soft);border-radius:9px;padding:11px 14px;margin-top:16px;line-height:1.55}
/* 제안서 작성기준 팝업 — 재설계(핵심값 칩 + 분류 카드) */
.speclist{padding:16px 18px 22px;overflow-y:auto;max-height:calc(92vh - 46px);background:#FAF9F7}
.spechd{font-size:13.5px;color:var(--muted);padding:12px 18px 4px;line-height:1.6}
.speckey{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:18px}
.keycard{background:#fff;border:1px solid var(--line);border-radius:12px;padding:12px 14px;box-shadow:0 1px 2px rgba(0,0,0,.03)}
.keycard .kl{font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--muted);text-transform:uppercase;margin-bottom:5px}
.keycard .kv{font-size:17.5px;font-weight:800;letter-spacing:-.02em;color:var(--ink)}
.keycard.hl{background:linear-gradient(135deg,#7A5AA6,#9575BE);border:0}
.keycard.hl .kl{color:rgba(255,255,255,.85)} .keycard.hl .kv{color:#fff}
.specsec{background:#fff;border:1px solid var(--line);border-radius:14px;margin-bottom:12px;overflow:hidden}
.specsec .sh{display:flex;align-items:center;gap:9px;padding:13px 18px;font-size:16.5px;font-weight:800;letter-spacing:-.01em;color:var(--ink);border-bottom:1px solid var(--soft)}
.specsec .sh .sd{width:10px;height:10px;border-radius:3px}
.specsec .sh .sc{margin-left:auto;font-size:13.5px;font-weight:700;color:var(--muted)}
.specsec ul{list-style:none;padding:8px 10px 12px}
.specsec li{position:relative;padding:9px 14px 9px 28px;font-size:16px;line-height:1.68;color:var(--ink2);border-radius:8px}
.specsec li:hover{background:var(--soft)}
.specsec li:before{content:"";position:absolute;left:13px;top:16px;width:6px;height:6px;border-radius:50%;background:var(--sc,#7A5AA6);opacity:.55}
.specsec li b{color:var(--ink);font-weight:700}
/* 서류 다운로드 팝업 */
.doclist{padding:8px 8px 12px;overflow-y:auto;max-height:calc(92vh - 46px)}
.docrow{display:flex;align-items:center;gap:12px;padding:12px 14px;border:1px solid var(--line);border-radius:10px;margin:8px;text-decoration:none;transition:.12s}
.docrow:hover{border-color:var(--accent);background:#FBFAF8}
.docext{flex-shrink:0;width:50px;height:33px;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:11.5px;font-weight:800;color:#fff;letter-spacing:.02em}
.docext.pdf{background:#D6493C} .docext.hwp{background:#2B7BB0} .docext.hwpx{background:#2B7BB0}
.docext.doc,.docext.docx{background:#2B579A} .docext.zip{background:#8C8C86} .docext.xls,.docext.xlsx{background:#2E9E5B}
.docnm{flex:1;font-size:14px;font-weight:600;color:var(--ink);word-break:break-all}
.docdl{flex-shrink:0;font-size:13px;font-weight:700;color:var(--accent)}
.docnote{font-size:12.5px;color:var(--muted);padding:2px 16px 10px}
/* 지역제한 게이트 칩 */
.gate{display:inline-block;padding:2px 8px;border-radius:6px;font-size:11.5px;font-weight:800;vertical-align:middle}
.gate.block{background:var(--rd-bg);color:var(--rd)}
.gate.ok{background:var(--bl-bg);color:var(--bl)}
/* 검색 키워드 패널 */
.kwbox{margin:16px 0 0;background:var(--card);border:1px solid var(--line);border-radius:14px;
 box-shadow:0 1px 2px rgba(0,0,0,.03),0 10px 26px -18px rgba(0,0,0,.12)}
.kwbox summary{cursor:pointer;list-style:none;padding:14px 18px;font-size:15px;font-weight:700;color:var(--ink);display:flex;align-items:center;gap:8px}
.kwbox summary::-webkit-details-marker{display:none}
.kwbox summary .cta{margin-left:auto;flex-shrink:0;white-space:nowrap;
 font-size:13px;color:var(--muted);font-weight:500}
.kwbox[open] summary .cta{color:var(--accent)}
.kwbody{padding:0 18px 16px}
.kwrow{margin:12px 0}
.kwlab{font-size:12.5px;font-weight:700;color:var(--muted);letter-spacing:.02em;margin-bottom:7px}
.kchip{display:inline-block;margin:3px 5px 0 0;padding:4px 11px;border-radius:20px;font-size:13px;font-weight:600}
.kchip.s{background:var(--accent-soft);color:var(--accent)}
.kchip.w{background:#F1EFEB;color:var(--ink2)}
.kchip.n{background:var(--rd-bg);color:var(--rd)}
/* 조합 키워드 — 단독으로는 효력이 없으므로 점선으로 구분한다 */
.kchip.sp{background:#EEF5FB;color:#2B6E9E;border:1px dashed #A8C8DE}
.kchip.di{background:#F0F7F1;color:#2E7D50;border:1px dashed #A9CDB5}
.kchip.ns{background:#FBF4E8;color:#8A6A24;border:1px dashed #D8BE86}
.kwand{display:inline-block;margin:3px 8px 0 4px;font-size:13.5px;font-weight:800;color:var(--muted)}
.kwmeta{font-size:13px;color:var(--muted);margin-top:12px;line-height:1.7;border-top:1px solid var(--line);padding-top:11px}
/* 보고서 팝업(모달) */
.modal{position:fixed;inset:0;background:rgba(20,18,16,.55);display:none;z-index:200;align-items:center;justify-content:center;padding:24px}
.modal.open{display:flex}
.modalbox{background:#fff;border-radius:16px;width:min(860px,96vw);height:92vh;position:relative;overflow:hidden;box-shadow:0 30px 80px -20px rgba(0,0,0,.5)}
.mbar{height:46px;display:flex;align-items:center;justify-content:space-between;padding:0 10px 0 18px;border-bottom:1px solid var(--line);background:#FAF9F7}
.mbar .mt{font-size:14px;font-weight:700;color:var(--ink2)}
.mclose{font-family:inherit;font-size:14.5px;font-weight:600;color:var(--ink2);background:#fff;border:1px solid var(--line);border-radius:8px;padding:6px 13px;cursor:pointer}
.mclose:hover{border-color:var(--accent);color:var(--accent)}
.modalbox iframe{width:100%;height:calc(92vh - 46px);border:0;background:#EDECE8}
.amt{font-weight:700;font-size:16.5px;white-space:nowrap}
.kw{color:var(--muted);font-size:12.5px;display:block;white-space:nowrap;
 overflow:hidden;text-overflow:ellipsis}
.clse{font-weight:600;font-size:14px;white-space:nowrap}
.dd{font-size:12.5px;color:var(--muted);margin-top:2px;white-space:nowrap}
.dd.near{color:var(--rd);font-weight:700}

/* 등급 pill */
.g{display:inline-block;padding:2px 7px;border-radius:6px;font-size:11.5px;font-weight:700}
.g-S{background:var(--ink);color:#fff}
.g-W{background:#F0EEEA;color:var(--muted)}
/* 신규(NEW) 뱃지 */
.newb{display:inline-block;padding:2px 7px;border-radius:6px;font-size:11.5px;font-weight:800;letter-spacing:.04em;
 background:var(--accent);color:#fff;vertical-align:middle;animation:newpulse 1.8s ease-in-out infinite}
@keyframes newpulse{0%,100%{box-shadow:0 0 0 0 rgba(233,102,58,.45)}50%{box-shadow:0 0 0 4px rgba(233,102,58,0)}}
/* 마감 임박 강조 */
.dd.urgent{color:var(--rd);font-weight:800}
tr.urgent-row td{background:var(--rd-bg)!important}
.dtag{display:inline-block;margin-top:3px;padding:1px 6px;border-radius:5px;font-size:11.5px;font-weight:800;background:var(--rd);color:#fff}
/* 판정 뱃지 */
.vb{display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border-radius:8px;font-size:13px;font-weight:700;white-space:nowrap}
.vb .vd{width:9px;height:9px;border-radius:50%}
.vb.go{background:var(--gn-bg);color:var(--gn)} .vb.go .vd{background:var(--gn)}
.vb.cond{background:var(--am-bg);color:var(--am)} .vb.cond .vd{background:var(--am)}
.vb.hold{background:#F1EFEB;color:var(--muted)} .vb.hold .vd{background:var(--muted)}
.vb.na{background:#F5F4F1;color:#B7B4AE} .vb.na .vd{background:#CFCCC6}
/* 자동 1차 분류 뱃지 — 사람 판정이 없는 건에만 붙는다. 판정과 헷갈리지 않도록 점선 테두리. */
.autob{display:inline-block;margin-top:5px;padding:2px 7px;border-radius:6px;font-size:12px;
 font-weight:700;letter-spacing:.02em;border:1px dashed;white-space:nowrap;cursor:help}
.autob.a-A{color:var(--accent);border-color:var(--accent);background:#FFF4F0}
.autob.a-B{color:#8A6A24;border-color:#D8BE86;background:#FBF6EA}
.autob.a-C{color:#9C9992;border-color:#DDD9D2;background:#F7F6F3}
/* 참가자격 뱃지 */
.qb{display:inline-block;margin-top:5px;padding:2px 7px;border-radius:6px;font-size:12px;
 font-weight:700;white-space:nowrap;cursor:help}
.qb.ok{background:var(--gn-bg);color:var(--gn)}
.qb.no{background:var(--rd-bg);color:var(--rd)}
.qb.na{background:#F1EFEB;color:var(--muted)}
.qb.blk{background:#2B2B2B;color:#fff}
/* 보유 자격 체크 패널 */
.qbox{margin:18px 0 12px;border:2px solid var(--accent);border-radius:14px;background:#fff;overflow:hidden;
 box-shadow:0 2px 14px -8px rgba(233,102,58,.5)}
.qttl{font-size:16px;font-weight:800;color:var(--accent);letter-spacing:-.02em}
.qttl::before{content:'\2713';display:inline-block;margin-right:7px;width:20px;height:20px;
 line-height:20px;text-align:center;border-radius:5px;background:var(--accent);color:#fff;font-size:13.5px}
.qsub{font-size:13.5px;color:var(--muted);font-weight:600}
.qbox summary{cursor:pointer;padding:13px 16px;font-size:14.5px;font-weight:700;list-style:none;display:flex;
 align-items:center;gap:8px;flex-wrap:wrap}
.qbox summary::-webkit-details-marker{display:none}
.qbody{padding:4px 16px 16px;border-top:1px solid var(--line)}
.qgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(272px,1fr));gap:6px 14px;margin:10px 0}
.qgrid label>span:not(.cnt){flex:1;min-width:0;word-break:keep-all}
.qgrid label{display:flex;align-items:center;gap:7px;font-size:14px;color:var(--ink2);cursor:pointer;
 padding:5px 7px;border-radius:8px}
.qgrid label:hover{background:var(--soft)}
.qgrid input{width:17px;height:17px;accent-color:var(--accent);cursor:pointer}
.qgrid .cnt{margin-left:auto;padding-left:8px;flex-shrink:0;white-space:nowrap;
 font-size:12.5px;color:var(--muted);font-variant-numeric:tabular-nums}
.qnote{font-size:13px;color:var(--muted);line-height:1.6;margin-top:6px}
.qacts{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap}
.qacts button{border:1px solid var(--line);background:#fff;border-radius:9px;padding:6px 12px;
 font-size:13.5px;font-weight:600;cursor:pointer;font-family:inherit;color:var(--ink2)}
.qacts button:hover{background:var(--soft)}
.qstat{font-size:13.5px;font-weight:700;color:var(--ink2);margin-left:auto;
 background:var(--accent-soft);padding:4px 10px;border-radius:8px;white-space:nowrap}
.brief{margin:16px 0 2px;font-size:14.5px;color:var(--ink2);background:#fff;border:1px solid var(--line);
 border-radius:12px;padding:12px 16px;display:flex;gap:18px;flex-wrap:wrap;align-items:center}
.brief>span{white-space:nowrap}
.brief>span:last-child{white-space:normal}
.brief b{font-weight:800}
.brief .go{color:var(--gn)} .brief .cond{color:var(--am)} .brief .near{color:var(--rd)}
.brief .sep{color:var(--line)}
/* 상태 점(●) */
.st{display:inline-flex;align-items:center;gap:7px;font-size:14px;font-weight:600;white-space:nowrap}
.st .d{width:9px;height:9px;border-radius:50%}
.st-자동추출{color:var(--gn)} .st-자동추출 .d{background:var(--gn)}
.st-규격서별도{color:var(--am)} .st-규격서별도 .d{background:var(--am)}
.st-첨부없음{color:var(--rd)} .st-첨부없음 .d{background:var(--rd)}
.reg{display:inline-block;padding:3px 8px;border-radius:7px;font-size:12.5px;font-weight:600;background:var(--bl-bg);color:var(--bl);white-space:nowrap}
/* v2.7 — 텍스트 확대에 따른 낱글자(외톨이 글자) 방지.
   짧은 라벨·뱃지·칩은 폭이 모자라도 쪼개지지 않게 하고, 셀은 줄바꿈 단위를 어절로 묶는다. */
.g,.gate,.newb,.dtag,.reg,.vb,.qb,.autob,.clse,.dd,.amt,.st,.kchip,.flab,
.seg .chip,.chips .chip,.kpi .l,.kpi .cap,.keycard .kl,.docext,.qstat,
thead th,.btn-report,.btn-start,.btn-g2b,.btn-doc,.btn-spec,.btn-wait,.btn-live,.btn-figma,
.pstep .pn,.acard h3,.ptitle,.qttl,.qsub{word-break:keep-all;overflow-wrap:normal}
/* 어절이 통째로 안 들어가는 긴 텍스트만 예외적으로 쪼갠다 */
.name,.org,.kw,.brow .bl,.qnote,.kwmeta,.docnm,.specsec li,.summary{word-break:keep-all;overflow-wrap:break-word}
/* ★ 외톨이 글자·외톨이 어절 방지 — 마지막 줄에 한 어절만 떨어지려 하면 브라우저가
   앞 줄에서 미리 한 어절을 넘겨 두 줄의 균형을 맞춘다. Chrome 117+.
   ⚠ text-wrap 은 '블록 컨테이너'에만 걸린다. span(.name·.kw)에 걸어도 듣지 않으므로
     body 에서 상속시키고 표 셀에도 명시한다. 미지원 브라우저는 종전 동작으로 되돌아간다. */
body,tbody td,thead th,.qnote,.kwmeta,.specsec li,.brief,.startnote,.foot{text-wrap:pretty}
/* v2.7b — 글자 크기 조절. zoom 은 폰트와 칸을 같은 비율로 키우므로
   확대해도 줄바꿈 지점이 바뀌지 않는다(낱글자가 새로 생기지 않는다). */
.fsbox{display:inline-flex;align-items:center;gap:7px;margin:14px 0 -4px;padding:5px 6px 5px 12px;
 background:#fff;border:1px solid var(--line);border-radius:12px}
.fslab{font-size:12px;font-weight:700;letter-spacing:.06em;color:var(--muted)}
.fsseg{display:inline-flex;background:var(--soft);border:1px solid var(--line);border-radius:10px;padding:3px;gap:2px}
.fsseg button{font-family:inherit;font-size:13px;font-weight:600;color:var(--muted);background:transparent;
 border:0;padding:5px 12px;border-radius:8px;cursor:pointer;white-space:nowrap;transition:.12s}
.fsseg button:hover{color:var(--ink2)}
.fsseg button.on{background:#fff;color:var(--ink);font-weight:700;
 box-shadow:0 0 0 1px rgba(0,0,0,.05),0 1px 2px -.5px rgba(0,0,0,.06),0 3px 3px -1.5px rgba(0,0,0,.04)}
.empty{padding:44px;text-align:center;color:var(--muted);font-size:14.5px}

.foot{margin-top:18px;font-size:13px;color:var(--muted);line-height:1.8}
.foot code{background:#E7E5E0;padding:1px 6px;border-radius:5px;font-size:12.5px}
@media(max-width:1080px){.kpis{grid-template-columns:1fr 1fr}}
@media(max-width:860px){.hide-sm{display:none}}
/* 폰 대응 — 대표가 이동 중에 폰으로 여는 화면이다.
   표가 7열이라 좁은 화면에서 글자가 뭉개지므로, 열을 단계적으로 접고
   그래도 넘치면 레이아웃을 깨뜨리는 대신 표 카드 안에서만 가로 스크롤시킨다. */
.tscroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
@media(max-width:640px){
 body{padding:20px 12px 44px}
 h1{font-size:25px}
 .sub{font-size:14px}
 .kpis{grid-template-columns:1fr 1fr;gap:10px;margin:18px 0 14px}
 .kpi{padding:15px 16px;min-height:96px;border-radius:15px}
 .kpi .n{font-size:27px} .kpi .l{font-size:13px} .kpi .cap{font-size:12px}
 .kpi .ic{display:none}
 .brief{gap:8px 12px;font-size:13.5px;padding:11px 13px}
 .acard{padding:16px 15px} .brow{grid-template-columns:76px 1fr 34px}
 .phead{padding:13px 12px 10px} .chips{padding:0 12px 10px}
 .search input{width:100%;max-width:none}
 .tools{width:100%}
 .search{width:100%}
 table{min-width:620px}          /* 이보다 좁아지면 표 안에서 가로 스크롤 */
 thead th,tbody td{padding:11px 12px}
 .hide-xs{display:none}
 .rlinks{gap:6px} .rlinks button,.rlinks a{font-size:13px;padding:5px 10px}
 .modal{padding:0}
 .modalbox{width:100vw;height:100vh;max-height:100vh;border-radius:0}
 .modalbox iframe{height:calc(100vh - 46px)}
}
</style></head>
<body><div class="wrap">
<div class="eyebrow">나라장터 · 공공디자인 공고 스캔</div>
<h1>수주 타깃 공고 대시보드</h1>
<div class="sub">스캔 기간 <b>__PERIOD__</b> · 전체 용역공고 <b class="mono">__RAW__</b>건 →
 필터 채택 <b class="mono">__N__</b>건 · 생성 __GEN__</div>
<div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
<div style="margin:14px 0 -4px"><a href="reports.html" style="display:inline-block;padding:9px 16px;background:var(--accent);color:#fff;border-radius:10px;text-decoration:none;font-weight:700;font-size:14.5px">과업분석 보고서 모음 (적극·조건부·보류) →</a></div>
<div class="fsbox"><span class="fslab">글자 크기</span><div class="fsseg" id="fsseg"><button data-z="1">보통</button><button data-z="1.12">크게</button><button data-z="1.25">아주 크게</button></div></div>
</div>
__KWPANEL__

<div class="brief">
 <span>오늘의 액션 →</span>
 <span><b class="go mono">__NGO__</b> 건 적극 검토</span><span class="sep">·</span>
 <span><b class="cond mono">__NCOND__</b> 건 조건부</span><span class="sep">·</span>
 <span>마감 D-7 이내 <b class="near mono">__NNEAR__</b> 건</span><span class="sep">·</span>
 <span>오늘 신규 <b class="mono" style="color:var(--accent)">__NNEW__</b> 건</span><span class="sep">·</span>
 <span style="color:var(--muted)">미분석 <b class="mono" style="color:var(--ink2)">__NNA__</b> 건<b class="mono" style="color:var(--accent)"> (자동 A __NNAA__ · B __NNAB__)</b></span>
 <span style="color:var(--muted);font-size:13.5px">— 판정순 → 자동분류순 정렬, 위에서부터 공략</span>
</div>

<div class="kpis">
 <div class="kpi hero">
   <div class="top"><span class="l">채택 타깃 공고</span>
     <span class="ic"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="1" fill="#fff" stroke="none"/></svg></span></div>
   <div><div class="n mono">__N__</div><div class="cap">전체 __RAW__건 중 선별</div></div>
 </div>
 <div class="kpi">
   <div class="top"><span class="l">적극 검토</span>
     <span class="ic"><svg viewBox="0 0 24 24"><path d="M5 13l4 4L19 7"/></svg></span></div>
   <div><div class="n mono" style="color:var(--gn)">__NGO__</div><div class="cap">바로 붙을 판</div></div>
 </div>
 <div class="kpi">
   <div class="top"><span class="l">조건부 검토</span>
     <span class="ic"><svg viewBox="0 0 24 24"><path d="M12 8v5m0 3h.01M10.3 3.9L2.4 18a2 2 0 001.7 3h15.8a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z"/></svg></span></div>
   <div><div class="n mono" style="color:var(--am)">__NCOND__</div><div class="cap">전제 해결 시</div></div>
 </div>
 <div class="kpi">
   <div class="top"><span class="l">부·울·경 관련</span>
     <span class="ic"><svg viewBox="0 0 24 24"><path d="M12 21s7-6.3 7-11a7 7 0 10-14 0c0 4.7 7 11 7 11z"/><circle cx="12" cy="10" r="2.4"/></svg></span></div>
   <div><div class="n mono">__NREGION__</div><div class="cap">지역 우선 타깃</div></div>
 </div>
 <div class="kpi">
   <div class="top"><span class="l">마감 임박</span>
     <span class="ic"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/></svg></span></div>
   <div><div class="n mono" style="color:__NEARCOL__">__NNEAR__</div><div class="cap">D-7 이내 · 최대 __MAXAMT__</div></div>
 </div>
</div>

<div class="analytics">
 <div class="acard">
   <h3>매칭 키워드 분포<span class="c">채택 __N__건 기준</span></h3>
   __KWBARS__
 </div>
 <div class="acard">
   <h3>RFP 확보경로 분포<span class="c">자동추출이 많을수록 자동화 유리</span></h3>
   __RFPBARS__
 </div>
</div>

__QUALPANEL__
<div class="panel">
 <div class="phead">
   <div class="ptitle">타깃 공고 <span class="c">총 __N__건</span></div>
   <div class="tools">
     <div class="search"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4-4"/></svg>
       <input id="q" placeholder="공고명·기관 검색" oninput="render()"></div>
   </div>
 </div>
 <div class="fbar">
   <div class="fgrp"><span class="flab">판정</span><div class="seg">
     <span class="chip on" data-k="verdict" data-v="">전체</span>
     <span class="chip" data-k="verdict" data-v="적극 검토">적극</span>
     <span class="chip" data-k="verdict" data-v="조건부 검토">조건부</span>
     <span class="chip" data-k="verdict" data-v="보류">보류</span>
     <span class="chip" data-k="verdict" data-v="__NA__">미분석</span>
   </div></div>
   <div class="fgrp"><span class="flab">자격</span><div class="seg">
     <span class="chip on" data-k="qual" data-v="">전체</span>
     <span class="chip" data-k="qual" data-v="ok">충족</span>
     <span class="chip" data-k="qual" data-v="no">부족</span>
   </div></div>
   <div class="fgrp"><span class="flab">마감</span><div class="seg">
     <span class="chip on" data-k="due" data-v="">전체</span>
     <span class="chip" data-k="due" data-v="near">임박 D-7</span>
     <span class="chip" data-k="due" data-v="new">신규</span>
   </div></div>
   <div class="fgrp"><span class="flab">지역</span><div class="seg">
     <span class="chip on" data-k="region" data-v="">전체</span>
     <span class="chip" data-k="region" data-v="1">부울경</span>
   </div></div>
   <div class="fgrp"><span class="flab">자동분류</span><div class="seg">
     <span class="chip on" data-k="auto" data-v="">전체</span>
     <span class="chip" data-k="auto" data-v="A">A</span>
     <span class="chip" data-k="auto" data-v="B">B</span>
     <span class="chip" data-k="auto" data-v="C">C</span>
   </div></div>
   <div class="fgrp"><span class="flab">RFP 확보</span><div class="seg">
     <span class="chip on" data-k="rfp" data-v="">전체</span>
     <span class="chip" data-k="rfp" data-v="자동추출">자동추출</span>
     <span class="chip" data-k="rfp" data-v="규격서별도">규격서별도</span>
     <span class="chip" data-k="rfp" data-v="첨부없음">첨부없음</span>
   </div></div>
 </div>
 <div class="tscroll">
 <table>
 <thead><tr>
   <th>판정</th><th>공고명 / 수요기관</th>
   <th class="sortable" data-s="amt">기초금액<span class="ar" id="ar-amt"></span></th>
   <th class="sortable" data-s="dday">마감<span class="ar" id="ar-dday"></span></th>
   <th class="hide-xs">RFP 확보</th><th class="hide-sm">지역</th><th class="hide-sm">매칭키워드</th>
 </tr></thead>
 <tbody id="tb"></tbody>
 </table>
 </div>
 <div class="empty" id="empty" style="display:none">조건에 맞는 공고가 없습니다.</div>
</div>

<div class="foot">
 <b>RFP 확보</b> — <span class="st st-자동추출"><span class="d"></span>자동추출</span> API에 제안요청서 포함, 즉시 텍스트화 ·
 <span class="st st-규격서별도"><span class="d"></span>규격서별도</span> 입찰공고서만, g2b 규격탭 브라우저 필요 ·
 <span class="st st-첨부없음"><span class="d"></span>첨부없음</span> 방문·전화 확인.<br>
 이 대시보드는 <code>g2b_scan.py</code> 실행 시점의 스냅샷입니다. 스캔을 다시 돌리면 최신 공고로 갱신됩니다.
</div>
</div>

<div class="modal" id="modal" onclick="if(event.target===this)closeModal()">
 <div class="modalbox">
   <div class="mbar"><span class="mt">과업분석 보고서</span><button class="mclose" onclick="closeModal()">닫기 ✕</button></div>
   <iframe id="mframe" src="about:blank"></iframe>
 </div>
</div>

<div class="modal" id="docmodal" onclick="if(event.target===this)closeDocs()">
 <div class="modalbox" style="height:auto;max-height:92vh">
   <div class="mbar"><span class="mt" id="doctitle" style="max-width:640px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">첨부 서류</span><button class="mclose" onclick="closeDocs()">닫기 ✕</button></div>
   <div class="docnote">과업지시서·제안요청서·공고문 원문입니다. 클릭하면 나라장터에서 바로 내려받습니다.</div>
   <div class="doclist" id="doclist"></div>
 </div>
</div>

<div class="modal" id="specmodal" onclick="if(event.target===this)closeSpec()">
 <div class="modalbox" style="height:auto;max-height:92vh">
   <div class="mbar"><span class="mt" id="spectitle" style="max-width:640px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">제안서 작성 기준</span><button class="mclose" onclick="closeSpec()">닫기 ✕</button></div>
   <div class="spechd">제안요청서에서 뽑은 <b>정성 제안서 작성 규격·유의사항</b>입니다(판형·매수·표지·제출방법·유의사항 등). 원문 대조 권장.</div>
   <div class="speclist" id="speclist"></div>
 </div>
</div>

<div class="modal" id="startmodal" onclick="if(event.target===this)closeStart()">
 <div class="modalbox" style="height:auto;max-height:92vh;width:min(680px,96vw)">
   <div class="mbar"><span class="mt">제안서 착수</span><button class="mclose" onclick="closeStart()">닫기 ✕</button></div>
   <div class="startbox">
     <h4 id="start-name">공고명</h4>
     <div class="sub">이 공고를 <b>제안서 진행</b>으로 선택합니다. 아래 명령을 복사해 클로드에 붙여넣으면 골격 → 승부처 원고 → 피그마까지 이어집니다.</div>
     <div class="pipeline">
       <div class="pstep"><div class="pn">STEP 1</div><div class="pt">초안 골격</div><div class="pd">Win Theme·배점역산·목차·페이지 핵심메시지</div></div>
       <div class="pstep"><div class="pn">STEP 2</div><div class="pt">승부처 원고</div><div class="pd">공간구성·기획연출 페이지별 4블록</div></div>
       <div class="pstep"><div class="pn">STEP 3</div><div class="pt">피그마 생성</div><div class="pd">하우스 표준 레이아웃으로 제안서 조립</div></div>
     </div>
     <div class="cmdbox" id="start-cmd"></div>
     <div class="copyrow">
       <button class="btn-copy" onclick="copyCmd()">📋 진행 명령 복사</button>
       <span class="copyhint" id="copyhint">복사해서 클로드에 붙여넣으세요.</span>
     </div>
     <div class="startnote">정적 대시보드라 클릭만으로 자동 생성되진 않습니다. 이 명령이 파이프라인의 트리거이고, 실행이 끝나면 이 공고는 <b>진행중</b> + 피그마 링크로 바뀝니다.</div>
   </div>
 </div>
</div>

<script>
const DATA = __DATA__;
const F = {verdict:"", rfp:"", region:"", due:"", auto:"", qual:""};
// ── 참가자격 게이트 (v2.4) ─────────────────────────────────────────────
// 우리가 '보유했다'고 체크한 자격만 충족으로 본다. 체크 전(미설정)에는 판정하지 않고
// 요건 개수만 중립 표시한다. 이 값은 채택 여부를 바꾸지 않는다 — 표시·필터 전용.
const QTAGS = __QTAGS__;
const HOME  = "__HOME__";
const QKEY  = "sigma_quals_v1";
let MY = {set:false, have:[]};
try { const v=JSON.parse(localStorage.getItem(QKEY)||"null"); if(v&&Array.isArray(v.have)) MY=v; } catch(e){}
function regionBlocked(d){
  if(!d.regLimit) return false;
  return !d.regLimit.split(/[,·\/]/).some(x=>x.trim() && HOME.includes(x.trim().slice(0,2)));
}
const SRC_NOTE = {"검수":"", "자동":"\n※ 규칙 기반 자동판독(실측 재현율 91%) — 최종 확인은 공고문 원문", "없음":""};
function qualState(d){
  const sn = SRC_NOTE[d.qsrc]||"";
  const auto = d.qsrc==="자동" ? " (자동)" : "";
  if(d.qsrc==="없음") return {cls:"na", label:"자격 미판독",
      tip:"이 공고는 제안요청서를 확보하지 못해 참가자격을 아직 읽지 못했다. 나라장터 공고문을 직접 확인할 것."};
  if(regionBlocked(d)) return {cls:"blk", label:"지역 배제"+auto,
      tip:"참가자격 본점 소재지 제한: "+d.regLimit+" (자사 "+HOME+")"+sn};
  if(d.qconf==="불확실") return {cls:"na", label:"자격 확인 필요",
      tip:"제안요청서 원문에서 참가자격 조항을 찾지 못했다. 나라장터 공고문을 직접 확인할 것."+sn};
  if(!(d.req||[]).length) return {cls:(d.qsrc==="자동"?"na":"ok"), label:"자격 문턱 없음"+auto,
      tip:"원문에서 별도 면허·업종등록 요건이 확인되지 않았다(나라장터 입찰참가자격 등록은 기본 전제)"+sn};
  const miss=(d.req||[]).filter(t=>!MY.have.includes(t));
  const names=t=>QTAGS[t]||t;
  if(!MY.set) return {cls:"na", label:"요건 "+d.req.length+"종"+auto,
      tip:"필요 자격: "+d.req.map(names).join(" · ")+"\n(위 「우리 보유 자격」에서 체크하면 충족 여부를 판정한다)"};
  if(!miss.length) return {cls:"ok", label:"자격 충족"+auto, tip:"필요 자격 전부 보유: "+d.req.map(names).join(" · ")+sn};
  return {cls:"no", label:"자격 부족 "+miss.length+auto, tip:"미보유: "+miss.map(names).join(" · ")+sn
      +(d.cons==="허용"?"\n→ 공동수급 허용 건이므로 파트너로 보완 가능":"")
      +(d.cons==="불허"?"\n⚠ 공동수급 불허 — 자체 보유가 아니면 참가 불가":"")};
}
let sortKey = null, sortDir = -1;   // 기본은 서버 판정순 유지, 헤더 클릭 시에만 정렬
document.querySelectorAll('.chip').forEach(c=>c.onclick=()=>{
 const k=c.dataset.k;
 document.querySelectorAll('.chip[data-k="'+k+'"]').forEach(x=>x.classList.remove('on'));
 c.classList.add('on'); F[k]=c.dataset.v; render();
});
document.querySelectorAll('th.sortable').forEach(th=>th.onclick=()=>{
 const s=th.dataset.s;
 if(sortKey===s) sortDir*=-1; else {sortKey=s; sortDir = s==="amt"?-1:1;}
 document.querySelectorAll('.ar').forEach(a=>a.textContent="");
 document.getElementById('ar-'+s).textContent = sortDir<0?"▼":"▲";
 render();
});
function render(){
 const q=(document.getElementById('q').value||"").trim().toLowerCase();
 let rows=DATA.filter(d=>{
   const near=d.dday!==null&&d.dday>=0&&d.dday<=7;
   const dueOk = !F.due || (F.due==="near"?near : F.due==="new"?d.isNew===true : true);
   // "__NA__" = 미분석(판정 없음). verdict가 빈 문자열이라 일반 비교로는 '전체'와 구분되지 않아 센티널을 쓴다.
   const vOk = !F.verdict || (F.verdict==="__NA__" ? !d.verdict : d.verdict===F.verdict);
   const qs=qualState(d);
   const qOk = !F.qual || (F.qual==="ok" ? qs.cls==="ok" : (qs.cls==="no"||qs.cls==="blk"));
   return vOk&&qOk&&(!F.rfp||d.rfp===F.rfp)&&(!F.auto||d.auto===F.auto)&&
   (!F.region||d.region===true)&&dueOk&&(!q||(d.name+d.org).toLowerCase().includes(q));
 });
 if(sortKey){rows.sort((a,b)=>{let av=a[sortKey]??-1e9,bv=b[sortKey]??-1e9;return (av<bv?-1:av>bv?1:0)*sortDir;});}
 document.getElementById('tb').innerHTML = rows.map(d=>{
   const near=d.dday!==null&&d.dday>=0&&d.dday<=7;
   const urgent=d.dday!==null&&d.dday>=0&&d.dday<=3;
   const ddTxt=d.dday===null?'':(d.dday<0?'마감':'D-'+d.dday);
   // 주 액션(솔리드) 1개 + 보조(아웃라인) 1개 + 아이콘 3개로 위계를 만든다
   const rbtn = d.report
       ? `<button class="btn-report" onclick="openReport('${d.no}',this)">과업분석 보고서</button>`
       : `<span class="btn-wait">분석 준비중</span>`;
   const gbtn = `<a class="ibtn" href="${d.url}" target="_blank" rel="noopener" title="나라장터 공고 원문 열기">${IC.link}</a>`;
   const dbtn = (d.docs&&d.docs.length)
       ? `<button class="ibtn" onclick="openDocs('${d.no}')" title="첨부 서류 ${d.docs.length}건 — 과업지시서·제안요청서·공고문">${IC.clip}<span class="num">${d.docs.length}</span></button>` : '';
   const sbtn = (d.spec&&d.spec.length)
       ? `<button class="ibtn" onclick="openSpec('${d.no}')" title="제안서 작성기준 — 판형·분량·제출방법·유의사항">${IC.doc}</button>` : '';
   const dec = d.decided||{};
   const startbtn = dec.status
       ? `<span class="btn-live"><span class="ld"></span>진행중</span>`+(dec.figma?`<a class="btn-figma" href="${dec.figma}" target="_blank" rel="noopener">피그마 ↗</a>`:'')
       : `<button class="btn-start" onclick="openStart('${d.no}')">제안서 착수 →</button>`;
   const nameClick = d.report ? `onclick="openReport('${d.no}',this)" style="cursor:pointer"` : '';
   const VC={'적극 검토':'go','조건부 검토':'cond','보류':'hold'};
   const vlab=d.verdict||'미분석'; const vcls=VC[d.verdict]||'na';
   const qst=qualState(d);
   // 사람 판정이 없는 건에만 자동 1차 분류를 보여준다. 판정을 대체하지 않는다.
   const autoTag = d.verdict ? '' :
     `<div class="autob a-${d.auto}" title="자동 1차 분류(규칙 기반, 판정 아님) — ${esc((d.autoWhy||[]).join(' · '))||'해당 없음'}">자동 ${d.auto}</div>`;
   const newBadge = d.isNew ? '<span class="newb">NEW</span> ' : '';
   const urgentTag = urgent ? '<span class="dtag">임박</span>' : '';
   const gateChip = d.gate==='block' ? ' <span class="gate block" title="'+esc(d.prtcpt)+'">타지역 전용</span>'
                  : d.gate==='ok' ? ' <span class="gate ok" title="'+esc(d.prtcpt)+'">지역제한</span>' : '';
   return `<tr class="${urgent?'urgent-row':''}">
    <td><span class="vb ${vcls}"><span class="vd"></span>${vlab}</span>${autoTag}
        <div class="qb ${qst.cls}" title="${esc(qst.tip)}">${qst.label}</div></td>
    <td>${newBadge}<span class="name" ${nameClick}>${esc(d.name)}</span> <span class="g g-${d.grade}">${d.grade}</span>${gateChip}
        <div class="org">${esc(d.org)}</div>
        <div class="rlinks">${rbtn}${startbtn}<span class="rsep"></span>${sbtn}${dbtn}${gbtn}</div></td>
    <td><span class="amt mono">${d.amtLabel}</span></td>
    <td><span class="clse mono">${(d.clse||'').slice(5,10)||'-'}</span><div class="dd ${urgent?'urgent':near?'near':''}">${ddTxt} ${urgentTag}</div></td>
    <td class="hide-xs"><span class="st st-${d.rfp}"><span class="d"></span>${d.rfp}</span></td>
    <td class="hide-sm">${d.region?'<span class="reg">부울경</span>':''}</td>
    <td class="hide-sm"><span class="kw" title="${esc((d.kw||'').split(',').join(', '))}">${esc((d.kw||'').split(',').join(', '))}</span></td>
   </tr>`;
 }).join('');
 document.getElementById('empty').style.display = rows.length?'none':'block';
}
const IC = {
  doc:'<svg viewBox="0 0 24 24"><path d="M14 3H7a1 1 0 00-1 1v16a1 1 0 001 1h10a1 1 0 001-1V7z"/><path d="M14 3v4h4"/><path d="M9 12h6M9 16h4"/></svg>',
  clip:'<svg viewBox="0 0 24 24"><path d="M16.5 7.5l-7 7a2.5 2.5 0 003.5 3.5l7.5-7.5a4.5 4.5 0 10-6.4-6.4L5.7 11.3a6.5 6.5 0 109.2 9.2l3.6-3.6"/></svg>',
  link:'<svg viewBox="0 0 24 24"><path d="M14 4h6v6"/><path d="M20 4l-9 9"/><path d="M10 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-4"/></svg>'
};
function esc(s){return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
function openReport(no){document.getElementById('mframe').src='report_'+no+'.html';
 document.getElementById('modal').classList.add('open');document.body.style.overflow='hidden';}
function closeModal(){document.getElementById('modal').classList.remove('open');
 document.getElementById('mframe').src='about:blank';document.body.style.overflow='';}
function openDocs(no){
 const d=DATA.find(x=>x.no===no); if(!d)return;
 const list=(d.docs||[]).map(f=>{
   const nm=f[0]||'첨부파일'; const url=f[1];
   const ext=(nm.split('.').pop()||'').toLowerCase().slice(0,4);
   return `<a class="docrow" href="${url}" target="_blank" rel="noopener">`
     +`<span class="docext ${ext}">${(ext||'FILE').toUpperCase()}</span>`
     +`<span class="docnm">${esc(nm)}</span><span class="docdl">내려받기 ↓</span></a>`;
 }).join('');
 document.getElementById('doclist').innerHTML=list||'<div style="padding:24px;color:#8C8C86;font-size:14.5px">첨부 서류가 없습니다.</div>';
 document.getElementById('doctitle').textContent=d.name;
 document.getElementById('docmodal').classList.add('open');document.body.style.overflow='hidden';}
function closeDocs(){document.getElementById('docmodal').classList.remove('open');document.body.style.overflow='';}
let _cmd="";
function openStart(no){
 const d=DATA.find(x=>x.no===no); if(!d)return;
 document.getElementById('start-name').textContent=d.name;
 _cmd=`나라장터 수주 대시보드 제안서 파이프라인 착수.\n공고: ${d.name}\n공고번호: ${no}\n기초금액: ${d.amtLabel} · 마감: ${(d.clse||'').slice(0,10)}\n\n다음을 순서대로 진행: ① 초안 골격(Win Theme·배점역산·목차·페이지 핵심메시지) ② 승부처 2·3장 페이지별 4블록 원고 ③ proposal-design-system 하우스 표준으로 피그마(root.gra's team) 제안서 생성. 완료 후 이 공고를 decisions.json에 진행중+피그마링크로 기록해줘.`;
 document.getElementById('start-cmd').textContent=_cmd;
 document.getElementById('copyhint').textContent='복사해서 클로드에 붙여넣으세요.';
 document.getElementById('startmodal').classList.add('open');document.body.style.overflow='hidden';}
function closeStart(){document.getElementById('startmodal').classList.remove('open');document.body.style.overflow='';}
function copyCmd(){navigator.clipboard.writeText(_cmd).then(()=>{document.getElementById('copyhint').textContent='✓ 복사됨 — 클로드에 붙여넣으세요.';}).catch(()=>{document.getElementById('copyhint').textContent='복사 실패 — 위 명령을 직접 선택해 복사하세요.';});}
function cleanSpec(s){return (s||'').replace(/^(※|[-•·]|[①-⑮]|[Ⅰ-Ⅹ]\.|\d+[.)]|\d+\)|[가-힣][.)])\s*/,'').trim();}
function openSpec(no){
 const d=DATA.find(x=>x.no===no); if(!d)return;
 const lines=(d.spec||[]).map(cleanSpec).filter(x=>x.length>3);
 const joined=lines.join('  ');
 // 핵심값 뽑기
 const key=[];
 const pan=joined.match(/A3|A4/i), dir=joined.match(/(가로|세로)[\s'"‘’“”]*로?[\s'"‘’“”]*(?:작성|규격|방향)/);
 const dirTxt=dir?dir[1]:'';
 if(pan) key.push(['판형', pan[0].toUpperCase()+(dirTxt?(' · '+dirTxt):'')]);
 const mae=joined.match(/(\d+)\s*매\s*이내/); if(mae) key.push(['분량', mae[1]+'매 이내']);
 const ins=joined.match(/(양면|단면)\s*인쇄|(단면|양면)/); if(ins) key.push(['인쇄', (ins[1]||ins[2])]);
 const usb=joined.match(/USB\s*(\d+)\s*매/); if(usb) key.push(['제출', 'USB '+usb[1]+'매']);
 // 분류
 const cats={규격:[],제출:[],평가:[],유의:[]};
 for(const ln of lines){
   if(/평가|배점|정성|정량|가격제안|심사|적격|커트/.test(ln)) cats.평가.push(ln);
   else if(/제출|부수|USB|마감|장소|등재|공공구매|반환|우편|방문/.test(ln)) cats.제출.push(ln);
   else if(/A3|A4|가로|세로|판형|규격|매\s*이내|\d+\s*매|쪽|면수|표지|목차|제본|인쇄|좌철|백상지|아트지|용지|글꼴|폰트|간지/.test(ln)) cats.규격.push(ln);
   else cats.유의.push(ln);
 }
 const SEC=[['규격','제안서 규격·판형','#7A5AA6'],['제출','제출 방법·부수','#2B7BB0'],['평가','평가·배점','#E9663A'],['유의','작성 유의사항','#C6871F']];
 let html='';
 if(key.length){
   html+='<div class="speckey">'+key.map((k,i)=>`<div class="keycard${i===0?' hl':''}"><div class="kl">${k[0]}</div><div class="kv">${esc(k[1])}</div></div>`).join('')+'</div>';
 }
 for(const [k,label,color] of SEC){
   const arr=cats[k]; if(!arr.length) continue;
   html+=`<div class="specsec"><div class="sh"><span class="sd" style="background:${color}"></span>${label}<span class="sc">${arr.length}</span></div><ul style="--sc:${color}">`
     + arr.map(x=>`<li>${esc(x)}</li>`).join('') + '</ul></div>';
 }
 document.getElementById('speclist').innerHTML=html||'<div style="padding:24px;color:#8C8C86;font-size:14.5px">작성 기준을 찾지 못했습니다. 원문(서류)을 확인하세요.</div>';
 document.getElementById('spectitle').textContent=d.name;
 document.getElementById('specmodal').classList.add('open');document.body.style.overflow='hidden';}
function closeSpec(){document.getElementById('specmodal').classList.remove('open');document.body.style.overflow='';}
// -- 보유 자격 체크 패널 --------------------------------------------
function qSave(){
  MY.have=[...document.querySelectorAll('.qgrid input:checked')].map(i=>i.dataset.t);
  MY.set=true;
  try{ localStorage.setItem(QKEY, JSON.stringify(MY)); }catch(e){}
  qStatus(); render();
}
function qStatus(){
  const el=document.getElementById('qstat'); if(!el) return;
  if(!MY.set){ el.textContent='미설정 - 체크하면 참가 가능 여부가 갈립니다'; return; }
  const n=DATA.filter(d=>qualState(d).cls==='ok').length;
  el.textContent='보유 '+MY.have.length+'종 선택 -> 자격 충족 '+n+' / '+DATA.length+'건';
}
function qAll(v){ document.querySelectorAll('.qgrid input').forEach(i=>i.checked=v); qSave(); }
function qReset(){
  MY={set:false,have:[]};
  try{ localStorage.removeItem(QKEY); }catch(e){}
  document.querySelectorAll('.qgrid input').forEach(i=>i.checked=false);
  qStatus(); render();
}
document.querySelectorAll('.qgrid input').forEach(i=>{
  i.checked = MY.have.includes(i.dataset.t);
  i.onchange = qSave;
});
// 아직 한 번도 설정하지 않았으면 패널을 펼쳐 둔다 — 못 찾고 지나치는 일을 막는다
if(!MY.set){ const qb=document.getElementById('qbox'); if(qb) qb.open=true; }
qStatus();
document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeModal();closeDocs();closeSpec();closeStart();}});
render();
/* ── 글자 크기 3단계 ─────────────────────────────────────────────────────
   폰트만 키우면 칸 폭이 그대로여서 글자가 쪼개진다. zoom 은 글자와 칸을
   같은 비율로 늘리므로 줄바꿈 위치가 바뀌지 않는다. */
const FSKEY='sigma_fs_v1';
function fsApply(z,save){
  document.body.style.zoom=z;
  document.querySelectorAll('#fsseg button').forEach(b=>b.classList.toggle('on',b.dataset.z===String(z)));
  if(save){ try{ localStorage.setItem(FSKEY,String(z)); }catch(e){} }
}
document.querySelectorAll('#fsseg button').forEach(b=>{
  b.onclick=()=>fsApply(b.dataset.z,true);
});
(function(){
  let z='1';
  try{ const v=localStorage.getItem(FSKEY); if(v) z=v; }catch(e){}
  fsApply(z,false);
})();
</script>
</body></html>"""

def bars(stat, maxn, colored=False):
    out = []
    for s in stat:
        w = round(s["n"] / maxn * 100)
        cls = (" " + s["c"]) if colored else ""
        out.append(
            f'<div class="brow"><div class="bl">{s["label"]}</div>'
            f'<div class="btrack"><div class="bfill{cls}" style="width:{w}%"></div></div>'
            f'<div class="bn">{s["n"]}건</div></div>')
    return "\n".join(out)

KWBARS = bars(KW_STAT, kw_max, colored=False)
RFPBARS = bars(RFP_STAT, max((s["n"] for s in RFP_STAT), default=1), colored=True)

# 검색 키워드 패널
import html as _html
def _kc(lst, cls):
    return "".join('<span class="kchip %s">%s</span>' % (cls, _html.escape(str(k))) for k in lst)
_strong = KWP.get("strong", []); _weak = KWP.get("weak", []); _neg_all = KWP.get("neg", [])
_space = KWP.get("space", []); _intent = KWP.get("design_intent", [])
_negsoft = KWP.get("neg_soft", []); _printonly = KWP.get("print_only", [])
# 조건부 제외(설계 3종)는 하드 제외와 성격이 달라 따로 보여준다
_neg = [k for k in _neg_all if k not in _negsoft]
_regions = KWP.get("regions", []); _minamt = KWP.get("min_amt", 0); _days = KWP.get("days_back", 0)
_combo = (
 ('<div class="kwrow"><div class="kwlab">조합 키워드 · <b>공간유형 %d개 × 디자인의도 %d개</b>가 '
  '<b>함께</b> 있을 때만 채택 (한쪽만으로는 안 잡는다)</div>%s<span class="kwand">AND</span>%s</div>')
 % (len(_space), len(_intent), _kc(_space,"sp"), _kc(_intent,"di"))
) if (_space and _intent) else ""
_soft = (
 ('<div class="kwrow"><div class="kwlab">조건부 제외 (%d) · 원래 제외어지만 <b>핵심 키워드가 함께 있으면 통과</b>'
  ' — 경관 과업이 「기본 및 실시설계」로 발주되는 경우 대응</div>%s</div>')
 % (len(_negsoft), _kc(_negsoft,"ns"))
) if _negsoft else ""
_prn = (
 ('<div class="kwrow"><div class="kwlab">인쇄물 조합 차단 (%d) · 보조 키워드가 <b>이 안에서만</b> 걸리면 제외'
  ' — 단순 인쇄물 제작 컷</div>%s</div>') % (len(_printonly), _kc(_printonly,"ns"))
) if _printonly else ""
KWPANEL = (
 '<details class="kwbox"><summary>🔎 이 대시보드가 자동으로 긁는 검색 키워드 '
 '<b style="color:var(--accent)">%d</b>개 <span class="cta">펼쳐보기 ▾</span></summary>'
 '<div class="kwbody">'
 '<div class="kwrow"><div class="kwlab">핵심 키워드 · 1개만 걸려도 채택 (%d)</div>%s</div>'
 '%s'
 '<div class="kwrow"><div class="kwlab">보조 키워드 · 2개 이상 겹치면 채택 (%d)</div>%s</div>'
 '%s'
 '<div class="kwrow"><div class="kwlab">제외 키워드 · 이 단어가 있으면 자동 제외 (%d)</div>%s</div>'
 '%s'
 '<div class="kwmeta">지역 태깅: %s 등 · 기초금액 하한 <b>%s원</b> · 최근 <b>%d일</b> 게시분 중 진행중(마감 전)만 · '
 '<b>참가자격·업종등록은 채택 조건에 넣지 않는다</b>(2026-07-30 결정 — 수집 우선, 응찰 판단은 사람이) · '
 '키워드 추가·수정은 스캐너(g2b_scan.py)에서 관리</div>'
 '</div></details>'
) % (len(_strong)+len(_weak)+len(_space)+len(_intent),
     len(_strong), _kc(_strong,"s"),
     _combo,
     len(_weak), _kc(_weak,"w"),
     _prn,
     len(_neg), _kc(_neg,"n"),
     _soft,
     ", ".join(_regions[:8]), won_fmt(_minamt), _days)

# 참가자격 체크 패널 (v2.4)
_qcnt = {}
for _d in data:
    for _t in _d["req"]:
        _qcnt[_t] = _qcnt.get(_t, 0) + 1
_order = sorted(QUAL_TAGS.items(), key=lambda kv: -_qcnt.get(kv[0], 0))
_boxes = "".join(
    '<label><input type="checkbox" data-t="%s"><span>%s</span><span class="cnt">%d건</span></label>'
    % (t, _html.escape(label), _qcnt.get(t, 0)) for t, label in _order)
_nlimit = sum(1 for _d in data if _d["regLimit"])
_ncons = sum(1 for _d in data if _d["cons"] == "불허")
QUALPANEL = (
    '<details class="qbox" id="qbox"><summary>'
    '<span class="qttl">우리 회사 업종·면허 체크</span>'
    '<span class="qsub">체크하면 참가 가능한 공고만 걸러 봅니다</span>'
    '<span class="qstat" id="qstat"></span></summary><div class="qbody">'
    '<div class="qnote">우리가 <b>실제로 보유한 업종등록·면허·증명서</b>만 체크하세요. '
    '체크한 것만 보유로 보고 각 공고에 「자격 충족 / 부족 N / 지역 배제」를 표시하며, '
    '바로 아래 표의 <b>자격 필터</b>(전체·충족·부족)가 함께 동작합니다. 선택은 이 브라우저에 저장됩니다.<br>'
    '<b>수집 자체는 자격과 무관하게 넓게 합니다</b> — 자격이 모자라 보이는 공고도 목록에서 지우지 않습니다'
    '(2026-07-30 결정). 공동수급 허용 건은 파트너로 보완할 수 있어 뱃지 설명에 함께 적어 둡니다.</div>'
    '<div class="qgrid">%s</div>'
    '<div class="qacts"><button onclick="qAll(true)">전부 보유</button>'
    '<button onclick="qReset()">초기화(미설정)</button></div>'
    '<div class="qnote">자사 본점 소재지 <b>%s</b> 기준. 현재 목록 중 '
    '<b>지역제한 %d건</b> · <b>공동수급 불허 %d건</b>.<br>'
    '자격 출처: <b>검수 %d건</b>(RFP 원문 정독) · <b>자동판독 %d건</b>(배치 규칙 기반, 재현율 실측 91%%) · '
    '<b>미판독 %d건</b>. 자동판독 건은 뱃지에 <b>(자동)</b>이 붙습니다 — 최종 확인은 공고문 원문으로 하세요.</div>'
    '</div></details>') % (_boxes, _html.escape(HOME_REGION), _nlimit, _ncons,
                           sum(1 for _d in data if _d["qsrc"]=="검수"),
                           sum(1 for _d in data if _d["qsrc"]=="자동"),
                           sum(1 for _d in data if _d["qsrc"]=="없음"))

HTML = (HTML.replace("__QUALPANEL__", QUALPANEL)
            .replace("__QTAGS__", json.dumps(QUAL_TAGS, ensure_ascii=False))
            .replace("__HOME__", HOME_REGION)
            .replace("__KWBARS__", KWBARS).replace("__RFPBARS__", RFPBARS).replace("__KWPANEL__", KWPANEL)
            .replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__RAW__", str(RAW_TOTAL)).replace("__PERIOD__", PERIOD or "-")
            .replace("__GEN__", GEN_AT or "-").replace("__N__", str(len(data)))
            .replace("__NS__", str(nS)).replace("__NAUTO__", str(nAuto))
            .replace("__NGO__", str(nGo)).replace("__NCOND__", str(nCond)).replace("__NNEAR__", str(nNear))
            .replace("__NNEW__", str(nNew)).replace("__NNA__", str(nNA))
            .replace("__NNAA__", str(nNAA)).replace("__NNAB__", str(nNAB))
            .replace("__NEARCOL__", "var(--rd)" if nNear else "var(--ink)")
            .replace("__NREGION__", str(nRegion)).replace("__MAXAMT__", maxAmt))
# GitHub Pages가 실제로 서빙하는 파일은 index.html이다. 예전에는 이 스크립트가
# g2b_dashboard.html만 쓰고 index.html 복사는 코드 밖(일일 배치)에서 이뤄져서,
# 로컬에서 빌드만 하면 화면이 안 바뀌는 것처럼 보이는 함정이 있었다. 여기서 같이 쓴다.
for _out in ("g2b_dashboard.html", "index.html"):
    open(_out, "w", encoding="utf-8").write(HTML)
print(f"g2b_dashboard.html + index.html 생성 · 채택 {len(data)} / 적극검토 {nGo} / 조건부 {nCond} / "
      f"마감임박(D-7) {nNear} · 미분석 {nNA} / 신규(NEW) {nNew} / 부울경 {nRegion} / 자동추출 {nAuto}")
