#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_bundle.py — reports_data/*.json(분석) → 단일 HTML(목록 + 13장 보고서 네비게이션)
출력: g2b_reports.html  (호진 형이 한 파일에서 훑고 클릭해서 열람/선택)
"""
import glob, json, re, html, build_report

VORDER = {"적극 검토": 0, "조건부 검토": 1, "보류": 2}
VCLS = {"적극 검토": "go", "조건부 검토": "cond", "보류": "hold"}

def esc(s): return html.escape(str(s))

docs = []
for f in sorted(glob.glob("reports_data/R26BK*.json")):
    d = json.load(open(f, encoding="utf-8"))
    docs.append(d)

def _num(s):
    m = re.search(r"([\d.]+)\s*억", str(s))
    if m: return float(m.group(1)) * 1e8
    m = re.search(r"([\d,]+)", str(s))
    return float(m.group(1).replace(",", "")) if m else 0

docs.sort(key=lambda d: (VORDER.get(d["fit"]["verdict"], 9), -_num(d.get("amt", ""))))

# 각 보고서 본문(.page) 추출 + 스타일 1회
STYLE = ""
pages = []
for d in docs:
    full = build_report.build(d)
    if not STYLE:
        STYLE = re.search(r"<style>.*?</style>", full, re.S).group(0)
    page = re.search(r'<div class="page">.*</div>\s*</body>', full, re.S).group(0)
    page = page.replace("</body>", "")
    pages.append((d["no"], page))

# 목록 항목
def cnt(v): return sum(1 for d in docs if d["fit"]["verdict"] == v)
items = ""
cur = None
for d in docs:
    v = d["fit"]["verdict"]
    if v != cur:
        cur = v
        items += f'<div class="grp"><span class="gdot {VCLS[v]}"></span>{esc(v)} <span class="gc">{cnt(v)}건</span></div>'
    reason = (d["fit"]["reasons"][0] if d["fit"].get("reasons") else "")
    items += (f'<div class="row {VCLS[v]}" onclick="show(\'{d["no"]}\')">'
              f'<div class="rname">{esc(d["name"])}</div>'
              f'<div class="rmeta">{esc(d["org"])} · {esc(d.get("amt",""))} · 마감 {esc(d.get("dday",""))}</div>'
              f'<div class="rwhy">{esc(reason)}</div></div>')

PAGES_HTML = "\n".join(
    f'<div class="rep" id="rep-{no}" style="display:none">'
    f'<button class="back" onclick="home()">← 목록으로</button>{page}</div>'
    for no, page in pages)

OUT = f"""<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>나라장터 수주 판단 보고서 모음</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">
{STYLE}
<style>
#list{{max-width:860px;margin:0 auto}}
.lhead{{margin-bottom:6px}}
.lhead .eb{{font-size:11px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;color:var(--accent)}}
.lhead h1{{font-size:26px;font-weight:800;letter-spacing:-.03em;margin:6px 0 4px}}
.lhead .s{{color:var(--muted);font-size:13px}}
.legend{{display:flex;gap:16px;margin:16px 0 22px;font-size:12px;color:var(--muted);flex-wrap:wrap}}
.legend span{{display:inline-flex;align-items:center;gap:6px}}
.grp{{font-size:13px;font-weight:800;letter-spacing:-.01em;margin:22px 0 8px;display:flex;align-items:center;gap:8px}}
.grp .gc{{color:var(--muted);font-weight:600;font-size:12px}}
.gdot{{width:10px;height:10px;border-radius:50%}} .gdot.go{{background:var(--go)}} .gdot.cond{{background:var(--cond)}} .gdot.hold{{background:var(--hold)}}
.row{{background:#fff;border:1px solid var(--line);border-left:3px solid var(--line);border-radius:12px;padding:14px 16px;margin:8px 0;cursor:pointer;transition:.12s}}
.row:hover{{box-shadow:0 8px 22px -14px rgba(0,0,0,.25);transform:translateY(-1px)}}
.row.go{{border-left-color:var(--go)}} .row.cond{{border-left-color:var(--cond)}} .row.hold{{border-left-color:var(--hold)}}
.rname{{font-size:14.5px;font-weight:700;letter-spacing:-.01em}}
.rmeta{{font-size:11.5px;color:var(--muted);margin-top:3px}}
.rwhy{{font-size:12px;color:var(--ink2);margin-top:6px;line-height:1.5}}
.back{{display:block;margin:0 auto 14px;max-width:210mm;width:100%;padding:9px;border:1px solid var(--line);
 background:#fff;border-radius:9px;font-family:inherit;font-size:13px;color:var(--ink2);cursor:pointer}}
.back:hover{{border-color:var(--accent);color:var(--accent)}}
body{{background:#EDECE8}}
@media print{{#list,.back{{display:none!important}} .rep{{display:block!important}}}}
</style></head><body>
<div id="list">
 <div class="lhead"><div class="eb">나라장터 · 공공디자인</div>
   <h1>수주 판단 보고서 모음</h1>
   <div class="s">자동추출 {len(docs)}건 · 각 공고 A4 과업분석보고서 · 생성 2026-07-18</div></div>
 <div class="legend">
   <span><span class="gdot go"></span>적극 검토 = 우리 역량 직결, 바로 붙을 판</span>
   <span><span class="gdot cond"></span>조건부 검토 = 자격·지역 등 전제 해결 시</span>
   <span><span class="gdot hold"></span>보류 = 자격·본질상 우리 일 아님</span>
 </div>
 {items}
 <div style="margin-top:26px;font-size:11px;color:var(--muted);line-height:1.7">
  판정은 RFP 원문 기반 분석 의견입니다. 팩트(배점·자격·일정)는 제안요청서에서 추출, 판정은 시그마애드 공공디자인·공간연출 역량 기준. 최종 결정 전 원문 대조 권장.</div>
</div>
{PAGES_HTML}
<script>
function show(no){{document.getElementById('list').style.display='none';
 document.querySelectorAll('.rep').forEach(r=>r.style.display='none');
 document.getElementById('rep-'+no).style.display='block';window.scrollTo(0,0);}}
function home(){{document.querySelectorAll('.rep').forEach(r=>r.style.display='none');
 document.getElementById('list').style.display='block';window.scrollTo(0,0);}}
</script>
</body></html>"""
open("g2b_reports.html", "w", encoding="utf-8").write(OUT)
g = cnt("적극 검토"); c = cnt("조건부 검토"); h = cnt("보류")
print(f"g2b_reports.html 생성 · 총 {len(docs)}건 (적극 {g} / 조건부 {c} / 보류 {h})")
