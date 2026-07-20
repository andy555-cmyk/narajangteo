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

def dday(clse):
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", clse or "")
    if not m: return None
    import datetime
    d = datetime.date(*map(int, m.groups()))
    return (d - datetime.date(2026, 7, 18)).days

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
    data.append({
        "grade": r["등급"], "rfp": r["RFP"], "region": r["지역매칭"] == "Y",
        "name": r["공고명"], "org": r["수요기관"], "amt": amt, "amtLabel": won_fmt(r["기초금액"]),
        "clse": (r["마감"] or "").strip(), "dday": dday(r["마감"]),
        "kw": r["키워드"], "no": no, "url": r["상세"],
        "report": f"report_{no}.html" if no in have_report else "",
        "verdict": verdicts.get(no, ""),
        "docs": ATT.get(no, []),
        "prtcpt": pr, "gate": region_gate,
    })
# 판정 우선 → 금액순 (붙을 것부터 위로)
data.sort(key=lambda x: (VRANK.get(x["verdict"], 3), -x["amt"]))

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
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@500;600&display=swap" rel="stylesheet">
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
 font-family:'Pretendard','Noto Sans KR',-apple-system,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;
 line-height:1.6;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;padding:34px 26px 60px}
.wrap{max-width:1180px;margin:0 auto}
.mono{font-variant-numeric:tabular-nums;font-family:'IBM Plex Mono','SF Mono',ui-monospace,Menlo,Consolas,monospace;letter-spacing:-.01em}

/* 헤더 */
.eyebrow{font-size:11px;font-weight:600;letter-spacing:.18em;text-transform:uppercase;color:var(--accent)}
h1{font-size:30px;font-weight:800;letter-spacing:-.035em;line-height:1.12;margin:7px 0 7px;color:var(--ink)}
.sub{color:var(--muted);font-size:13.5px}
.sub b{color:var(--ink2);font-weight:600}

/* KPI bento */
.kpis{display:grid;grid-template-columns:1.35fr 1fr 1fr 1fr 1fr;gap:14px;margin:26px 0 20px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:20px 22px;
 box-shadow:0 1px 2px rgba(0,0,0,.03),0 10px 26px -16px rgba(0,0,0,.14);position:relative;min-height:120px;
 display:flex;flex-direction:column;justify-content:space-between}
.kpi.hero{background:linear-gradient(135deg,var(--accent) 0%,var(--accent-2) 100%);border:0;color:#fff}
.kpi .top{display:flex;justify-content:space-between;align-items:flex-start}
.kpi .l{font-size:12.5px;color:var(--muted);font-weight:500}
.kpi.hero .l{color:rgba(255,255,255,.9)}
.kpi .ic{width:30px;height:30px;border-radius:9px;background:#F6F4F0;display:flex;align-items:center;justify-content:center}
.kpi.hero .ic{background:rgba(255,255,255,.2)}
.kpi .ic svg{width:16px;height:16px;stroke:var(--muted);fill:none;stroke-width:1.7}
.kpi.hero .ic svg{stroke:#fff}
.kpi .n{font-size:32px;font-weight:800;letter-spacing:-.03em;line-height:1}
.kpi .cap{font-size:11.5px;color:var(--muted);margin-top:5px}
.kpi.hero .cap{color:rgba(255,255,255,.85)}

/* 분석(가로 막대) */
.analytics{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:20px}
.acard{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:20px 22px;
 box-shadow:0 1px 2px rgba(0,0,0,.03),0 10px 26px -16px rgba(0,0,0,.14)}
.acard h3{font-size:13.5px;font-weight:700;letter-spacing:-.01em;margin-bottom:16px}
.acard h3 .c{color:var(--muted);font-weight:500;font-size:12px;margin-left:5px}
.brow{display:grid;grid-template-columns:96px 1fr 40px;align-items:center;gap:10px;margin:9px 0}
.brow .bl{font-size:12px;color:var(--ink2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.btrack{height:9px;background:#F1EFEB;border-radius:6px;overflow:hidden}
.bfill{height:100%;border-radius:6px;background:linear-gradient(90deg,var(--accent),var(--accent-2))}
.bfill.gn{background:var(--gn)} .bfill.am{background:var(--am)} .bfill.rd{background:var(--rd)}
.brow .bn{font-size:12px;font-weight:700;text-align:right;color:var(--ink2)}
@media(max-width:860px){.analytics{grid-template-columns:1fr}}

/* 테이블 카드 */
.panel{background:var(--card);border:1px solid var(--line);border-radius:20px;padding:8px 8px 8px;
 box-shadow:0 1px 2px rgba(0,0,0,.03),0 14px 34px -20px rgba(0,0,0,.16)}
.phead{display:flex;justify-content:space-between;align-items:center;gap:14px;padding:16px 16px 12px;flex-wrap:wrap}
.ptitle{font-size:16px;font-weight:700;letter-spacing:-.02em}
.ptitle .c{color:var(--muted);font-weight:500;font-size:13px;margin-left:6px}
.tools{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.search{position:relative}
.search input{width:210px;max-width:48vw;padding:8px 13px 8px 32px;border:1px solid var(--line);border-radius:22px;
 font-size:13px;font-family:inherit;background:#FAF9F7;color:var(--ink)}
.search input:focus{outline:none;border-color:var(--accent);background:#fff}
.search svg{position:absolute;left:11px;top:9px;width:14px;height:14px;stroke:var(--muted);fill:none;stroke-width:1.8}

.chips{display:flex;gap:6px;align-items:center;flex-wrap:wrap;padding:0 16px 12px}
.chips .lab{font-size:11px;color:var(--muted);margin:0 3px}
.chip{padding:6px 12px;border:1px solid var(--line);border-radius:20px;background:#fff;
 font-size:12.5px;color:var(--ink2);cursor:pointer;transition:.12s}
.chip:hover{border-color:var(--accent-2)}
.chip.on{background:var(--ink);border-color:var(--ink);color:#fff;font-weight:600}

table{width:100%;border-collapse:collapse;font-size:13px}
thead th{text-align:left;padding:11px 16px;font-size:11px;font-weight:600;letter-spacing:.03em;
 text-transform:uppercase;color:var(--muted);border-top:1px solid var(--line);border-bottom:1px solid var(--line);
 background:#FAF9F7;white-space:nowrap}
thead th.sortable{cursor:pointer;user-select:none}
thead th.sortable:hover{color:var(--accent)}
thead th .ar{opacity:.55;font-size:9px;margin-left:2px}
tbody td{padding:14px 16px;border-bottom:1px solid var(--line);vertical-align:middle}
tbody tr:last-child td{border-bottom:0}
tbody tr:hover{background:#FBFAF8}
.name{font-weight:600;color:var(--ink);text-decoration:none;letter-spacing:-.01em;font-size:13.5px}
.name:hover{color:var(--accent);text-decoration:underline}
.org{color:var(--muted);font-size:11.5px;margin-top:3px}
.name{cursor:default}
.rlinks{margin-top:8px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.btn-report{font-family:inherit;font-size:12px;font-weight:700;color:#fff;background:var(--accent);border:0;padding:6px 13px;border-radius:8px;cursor:pointer;transition:.12s}
.btn-report:hover{filter:brightness(.94)}
.btn-g2b{font-size:12px;font-weight:600;color:var(--ink2);text-decoration:none;background:#fff;border:1px solid var(--line);padding:6px 12px;border-radius:8px}
.btn-g2b:hover{border-color:var(--accent);color:var(--accent)}
.btn-wait{font-size:12px;font-weight:600;color:var(--muted);background:#F1EFEB;padding:6px 12px;border-radius:8px}
.btn-doc{font-family:inherit;font-size:12px;font-weight:600;color:var(--bl);background:var(--bl-bg);border:1px solid #CBE0F0;padding:6px 12px;border-radius:8px;cursor:pointer}
.btn-doc:hover{filter:brightness(.97)}
/* 서류 다운로드 팝업 */
.doclist{padding:8px 8px 12px;overflow-y:auto;max-height:calc(92vh - 46px)}
.docrow{display:flex;align-items:center;gap:12px;padding:12px 14px;border:1px solid var(--line);border-radius:10px;margin:8px;text-decoration:none;transition:.12s}
.docrow:hover{border-color:var(--accent);background:#FBFAF8}
.docext{flex-shrink:0;width:44px;height:30px;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:800;color:#fff;letter-spacing:.02em}
.docext.pdf{background:#D6493C} .docext.hwp{background:#2B7BB0} .docext.hwpx{background:#2B7BB0}
.docext.doc,.docext.docx{background:#2B579A} .docext.zip{background:#8C8C86} .docext.xls,.docext.xlsx{background:#2E9E5B}
.docnm{flex:1;font-size:12.5px;font-weight:600;color:var(--ink);word-break:break-all}
.docdl{flex-shrink:0;font-size:11.5px;font-weight:700;color:var(--accent)}
.docnote{font-size:11px;color:var(--muted);padding:2px 16px 10px}
/* 지역제한 게이트 칩 */
.gate{display:inline-block;padding:2px 8px;border-radius:6px;font-size:10px;font-weight:800;vertical-align:middle}
.gate.block{background:var(--rd-bg);color:var(--rd)}
.gate.ok{background:var(--bl-bg);color:var(--bl)}
/* 보고서 팝업(모달) */
.modal{position:fixed;inset:0;background:rgba(20,18,16,.55);display:none;z-index:200;align-items:center;justify-content:center;padding:24px}
.modal.open{display:flex}
.modalbox{background:#fff;border-radius:16px;width:min(860px,96vw);height:92vh;position:relative;overflow:hidden;box-shadow:0 30px 80px -20px rgba(0,0,0,.5)}
.mbar{height:46px;display:flex;align-items:center;justify-content:space-between;padding:0 10px 0 18px;border-bottom:1px solid var(--line);background:#FAF9F7}
.mbar .mt{font-size:12.5px;font-weight:700;color:var(--ink2)}
.mclose{font-family:inherit;font-size:13px;font-weight:600;color:var(--ink2);background:#fff;border:1px solid var(--line);border-radius:8px;padding:6px 13px;cursor:pointer}
.mclose:hover{border-color:var(--accent);color:var(--accent)}
.modalbox iframe{width:100%;height:calc(92vh - 46px);border:0;background:#EDECE8}
.amt{font-weight:700;font-size:15px;white-space:nowrap}
.kw{color:var(--muted);font-size:11px}
.clse{font-weight:600;font-size:12.5px}
.dd{font-size:11px;color:var(--muted);margin-top:2px}
.dd.near{color:var(--rd);font-weight:700}

/* 등급 pill */
.g{display:inline-block;padding:2px 7px;border-radius:6px;font-size:10px;font-weight:700}
.g-S{background:var(--ink);color:#fff}
.g-W{background:#F0EEEA;color:var(--muted)}
/* 신규(NEW) 뱃지 */
.newb{display:inline-block;padding:2px 7px;border-radius:6px;font-size:9.5px;font-weight:800;letter-spacing:.04em;
 background:var(--accent);color:#fff;vertical-align:middle;animation:newpulse 1.8s ease-in-out infinite}
@keyframes newpulse{0%,100%{box-shadow:0 0 0 0 rgba(233,102,58,.45)}50%{box-shadow:0 0 0 4px rgba(233,102,58,0)}}
/* 마감 임박 강조 */
.dd.urgent{color:var(--rd);font-weight:800}
tr.urgent-row td{background:var(--rd-bg)!important}
.dtag{display:inline-block;margin-top:3px;padding:1px 6px;border-radius:5px;font-size:9.5px;font-weight:800;background:var(--rd);color:#fff}
/* 판정 뱃지 */
.vb{display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border-radius:8px;font-size:11.5px;font-weight:700;white-space:nowrap}
.vb .vd{width:8px;height:8px;border-radius:50%}
.vb.go{background:var(--gn-bg);color:var(--gn)} .vb.go .vd{background:var(--gn)}
.vb.cond{background:var(--am-bg);color:var(--am)} .vb.cond .vd{background:var(--am)}
.vb.hold{background:#F1EFEB;color:var(--muted)} .vb.hold .vd{background:var(--muted)}
.vb.na{background:#F5F4F1;color:#B7B4AE} .vb.na .vd{background:#CFCCC6}
.brief{margin:16px 0 2px;font-size:13px;color:var(--ink2);background:#fff;border:1px solid var(--line);
 border-radius:12px;padding:12px 16px;display:flex;gap:18px;flex-wrap:wrap;align-items:center}
.brief b{font-weight:800}
.brief .go{color:var(--gn)} .brief .cond{color:var(--am)} .brief .near{color:var(--rd)}
.brief .sep{color:var(--line)}
/* 상태 점(●) */
.st{display:inline-flex;align-items:center;gap:7px;font-size:12.5px;font-weight:600;white-space:nowrap}
.st .d{width:8px;height:8px;border-radius:50%}
.st-자동추출{color:var(--gn)} .st-자동추출 .d{background:var(--gn)}
.st-규격서별도{color:var(--am)} .st-규격서별도 .d{background:var(--am)}
.st-첨부없음{color:var(--rd)} .st-첨부없음 .d{background:var(--rd)}
.reg{display:inline-block;padding:3px 8px;border-radius:7px;font-size:11px;font-weight:600;background:var(--bl-bg);color:var(--bl)}
.empty{padding:44px;text-align:center;color:var(--muted);font-size:13px}

.foot{margin-top:18px;font-size:11.5px;color:var(--muted);line-height:1.8}
.foot code{background:#E7E5E0;padding:1px 6px;border-radius:5px;font-size:11px}
@media(max-width:860px){.kpis{grid-template-columns:1fr 1fr}.hide-sm{display:none}}
</style></head>
<body><div class="wrap">
<div class="eyebrow">나라장터 · 공공디자인 공고 스캔</div>
<h1>수주 타깃 공고 대시보드</h1>
<div class="sub">스캔 기간 <b>__PERIOD__</b> · 전체 용역공고 <b class="mono">__RAW__</b>건 →
 필터 채택 <b class="mono">__N__</b>건 · 생성 __GEN__</div>
<div style="margin:14px 0 -4px"><a href="reports.html" style="display:inline-block;padding:9px 16px;background:var(--accent);color:#fff;border-radius:10px;text-decoration:none;font-weight:700;font-size:13px">과업분석 보고서 모음 (적극·조건부·보류) →</a></div>

<div class="brief">
 <span>오늘의 액션 →</span>
 <span><b class="go mono">__NGO__</b> 건 적극 검토</span><span class="sep">·</span>
 <span><b class="cond mono">__NCOND__</b> 건 조건부</span><span class="sep">·</span>
 <span>마감 D-7 이내 <b class="near mono">__NNEAR__</b> 건</span><span class="sep">·</span>
 <span>오늘 신규 <b class="mono" style="color:var(--accent)">__NNEW__</b> 건</span>
 <span style="color:var(--muted);font-size:12px">— 판정순 정렬, 위에서부터 공략</span>
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
   <div class="top"><span class="l">최대 기초금액</span>
     <span class="ic"><svg viewBox="0 0 24 24"><ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6"/></svg></span></div>
   <div><div class="n mono">__MAXAMT__</div><div class="cap">단일 공고 최대</div></div>
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

<div class="panel">
 <div class="phead">
   <div class="ptitle">타깃 공고 <span class="c">총 __N__건</span></div>
   <div class="tools">
     <div class="search"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4-4"/></svg>
       <input id="q" placeholder="공고명·기관 검색" oninput="render()"></div>
   </div>
 </div>
 <div class="chips">
   <span class="lab">판정</span>
   <span class="chip on" data-k="verdict" data-v="">전체</span>
   <span class="chip" data-k="verdict" data-v="적극 검토">적극 검토</span>
   <span class="chip" data-k="verdict" data-v="조건부 검토">조건부</span>
   <span class="chip" data-k="verdict" data-v="보류">보류</span>
   <span class="lab" style="margin-left:8px">RFP</span>
   <span class="chip on" data-k="rfp" data-v="">전체</span>
   <span class="chip" data-k="rfp" data-v="자동추출">자동추출</span>
   <span class="chip" data-k="rfp" data-v="규격서별도">규격서별도</span>
   <span class="chip" data-k="rfp" data-v="첨부없음">첨부없음</span>
   <span class="lab" style="margin-left:8px">지역</span>
   <span class="chip on" data-k="region" data-v="">전체</span>
   <span class="chip" data-k="region" data-v="1">부울경</span>
   <span class="lab" style="margin-left:8px">마감</span>
   <span class="chip on" data-k="due" data-v="">전체</span>
   <span class="chip" data-k="due" data-v="near">임박 D-7</span>
   <span class="chip" data-k="due" data-v="new">신규 NEW</span>
 </div>
 <table>
 <thead><tr>
   <th>판정</th><th>공고명 / 수요기관</th>
   <th class="sortable" data-s="amt">기초금액<span class="ar" id="ar-amt"></span></th>
   <th class="sortable" data-s="dday">마감<span class="ar" id="ar-dday"></span></th>
   <th>RFP 확보</th><th class="hide-sm">지역</th><th class="hide-sm">매칭키워드</th>
 </tr></thead>
 <tbody id="tb"></tbody>
 </table>
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

<script>
const DATA = __DATA__;
const F = {verdict:"", rfp:"", region:"", due:""};
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
   return (!F.verdict||d.verdict===F.verdict)&&(!F.rfp||d.rfp===F.rfp)&&
   (!F.region||d.region===true)&&dueOk&&(!q||(d.name+d.org).toLowerCase().includes(q));
 });
 if(sortKey){rows.sort((a,b)=>{let av=a[sortKey]??-1e9,bv=b[sortKey]??-1e9;return (av<bv?-1:av>bv?1:0)*sortDir;});}
 document.getElementById('tb').innerHTML = rows.map(d=>{
   const near=d.dday!==null&&d.dday>=0&&d.dday<=7;
   const urgent=d.dday!==null&&d.dday>=0&&d.dday<=3;
   const ddTxt=d.dday===null?'':(d.dday<0?'마감':'D-'+d.dday);
   const rbtn = d.report
       ? `<button class="btn-report" onclick="openReport('${d.no}',this)">과업분석 보고서</button>`
       : `<span class="btn-wait">분석 준비중</span>`;
   const gbtn = `<a class="btn-g2b" href="${d.url}" target="_blank" rel="noopener">나라장터 ↗</a>`;
   const dbtn = (d.docs&&d.docs.length) ? `<button class="btn-doc" onclick="openDocs('${d.no}')">📎 서류 ${d.docs.length}</button>` : '';
   const nameClick = d.report ? `onclick="openReport('${d.no}',this)" style="cursor:pointer"` : '';
   const VC={'적극 검토':'go','조건부 검토':'cond','보류':'hold'};
   const vlab=d.verdict||'미분석'; const vcls=VC[d.verdict]||'na';
   const newBadge = d.isNew ? '<span class="newb">NEW</span> ' : '';
   const urgentTag = urgent ? '<span class="dtag">임박</span>' : '';
   const gateChip = d.gate==='block' ? ' <span class="gate block" title="'+esc(d.prtcpt)+'">타지역 전용</span>'
                  : d.gate==='ok' ? ' <span class="gate ok" title="'+esc(d.prtcpt)+'">지역제한</span>' : '';
   return `<tr class="${urgent?'urgent-row':''}">
    <td><span class="vb ${vcls}"><span class="vd"></span>${vlab}</span></td>
    <td>${newBadge}<span class="name" ${nameClick}>${esc(d.name)}</span> <span class="g g-${d.grade}">${d.grade}</span>${gateChip}
        <div class="org">${esc(d.org)}</div>
        <div class="rlinks">${rbtn}${dbtn}${gbtn}</div></td>
    <td><span class="amt mono">${d.amtLabel}</span></td>
    <td><span class="clse mono">${(d.clse||'').slice(5,10)||'-'}</span><div class="dd ${urgent?'urgent':near?'near':''}">${ddTxt} ${urgentTag}</div></td>
    <td><span class="st st-${d.rfp}"><span class="d"></span>${d.rfp}</span></td>
    <td class="hide-sm">${d.region?'<span class="reg">부울경</span>':''}</td>
    <td class="hide-sm"><span class="kw">${esc(d.kw)}</span></td>
   </tr>`;
 }).join('');
 document.getElementById('empty').style.display = rows.length?'none':'block';
}
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
 document.getElementById('doclist').innerHTML=list||'<div style="padding:24px;color:#8C8C86;font-size:13px">첨부 서류가 없습니다.</div>';
 document.getElementById('doctitle').textContent=d.name;
 document.getElementById('docmodal').classList.add('open');document.body.style.overflow='hidden';}
function closeDocs(){document.getElementById('docmodal').classList.remove('open');document.body.style.overflow='';}
document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeModal();closeDocs();}});
render();
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

HTML = (HTML.replace("__KWBARS__", KWBARS).replace("__RFPBARS__", RFPBARS)
            .replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__RAW__", str(RAW_TOTAL)).replace("__PERIOD__", PERIOD or "-")
            .replace("__GEN__", GEN_AT or "-").replace("__N__", str(len(data)))
            .replace("__NS__", str(nS)).replace("__NAUTO__", str(nAuto))
            .replace("__NGO__", str(nGo)).replace("__NCOND__", str(nCond)).replace("__NNEAR__", str(nNear))
            .replace("__NNEW__", str(nNew))
            .replace("__NREGION__", str(nRegion)).replace("__MAXAMT__", maxAmt))
open("g2b_dashboard.html", "w", encoding="utf-8").write(HTML)
print(f"g2b_dashboard.html 생성 · 채택 {len(data)} / 적극검토 {nGo} / 조건부 {nCond} / "
      f"마감임박(D-7) {nNear} / 신규(NEW) {nNew} / 부울경 {nRegion} / 자동추출 {nAuto}")
