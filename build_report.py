#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_report.py — 공고 분석 JSON → A4 1페이지 과업분석보고서 HTML
용도: 수주 후보 공고별로 "붙을까 말까"를 판단하는 의사결정 원페이저.
입력: reports_data/<공고번호>.json (아래 스키마)
출력: report_<공고번호>.html  (화면 열람 + 인쇄시 A4 1장)
사용: python3 build_report.py reports_data/R26BK01632179.json
"""
import json, sys, html

VERDICT_CLASS = {"적극 검토": "go", "조건부 검토": "cond", "보류": "hold"}

def esc(s): return html.escape(str(s))

def build(d):
    ov = "".join(f"<tr><th>{esc(k)}</th><td>{esc(v)}</td></tr>" for k, v in d["overview"])
    scope = "".join(f"<li>{esc(s)}</li>" for s in d["scope"])
    # 배점
    srows = ""
    for r in d["scoring"]["rows"]:
        hi = " hi" if r.get("key") else ""
        srows += (f'<tr class="{hi.strip()}"><td>{esc(r["group"])}</td>'
                  f'<td>{esc(r["item"])}</td><td class="pt mono">{esc(r["pt"])}</td></tr>')
    qual = "".join(f"<li>{esc(q)}</li>" for q in d["qualification"])
    reasons = "".join(f"<li>{esc(x)}</li>" for x in d["fit"]["reasons"])
    risks = "".join(f"<li>{esc(x)}</li>" for x in d["fit"]["risks"])
    sched = "".join(f"<tr><td>{esc(a)}</td><td class='mono'>{esc(b)}</td></tr>" for a, b in d["schedule"])
    vclass = VERDICT_CLASS.get(d["fit"]["verdict"], "cond")

    return TPL.replace("{{TITLE}}", esc(d["name"])) \
        .replace("{{NO}}", esc(d["no"])).replace("{{GEN}}", esc(d.get("gen", ""))) \
        .replace("{{ORG}}", esc(d["org"])).replace("{{AMT}}", esc(d["amt"])) \
        .replace("{{DDAY}}", esc(d.get("dday", ""))).replace("{{OVERVIEW}}", ov) \
        .replace("{{SUMMARY}}", esc(d["summary"])).replace("{{SCOPE}}", scope) \
        .replace("{{SCORING}}", srows).replace("{{SCORENOTE}}", esc(d["scoring"].get("note", ""))) \
        .replace("{{QUAL}}", qual).replace("{{VERDICT}}", esc(d["fit"]["verdict"])) \
        .replace("{{VCLASS}}", vclass).replace("{{REASONS}}", reasons).replace("{{RISKS}}", risks) \
        .replace("{{SCHED}}", sched).replace("{{SRC}}", esc(d.get("source", "")))

TPL = r"""<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>과업분석보고서 · {{TITLE}}</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">
<style>
:root{--ink:#1A1A1A;--ink2:#3A3A38;--muted:#8C8C86;--line:#E7E5E0;--soft:#FAF9F7;
 --accent:#E9663A;--go:#2E9E5B;--go-bg:#E9F6EF;--cond:#C6871F;--cond-bg:#FBF1DC;--hold:#D6493C;--hold-bg:#FBE7E4;}
*{box-sizing:border-box;margin:0;padding:0}
body{background:#EDECE8;font-family:'Pretendard','Noto Sans KR',-apple-system,'Malgun Gothic',sans-serif;
 color:var(--ink);line-height:1.5;padding:24px;-webkit-font-smoothing:antialiased}
.mono{font-family:'IBM Plex Mono',ui-monospace,monospace;font-variant-numeric:tabular-nums}
.page{width:210mm;min-height:297mm;margin:0 auto;background:#fff;padding:16mm 15mm;
 box-shadow:0 4px 30px -10px rgba(0,0,0,.25)}
.top{display:flex;justify-content:space-between;align-items:flex-start;border-bottom:2px solid var(--ink);padding-bottom:11px}
.eyebrow{font-size:10.5px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;color:var(--accent)}
h1{font-size:20px;font-weight:800;letter-spacing:-.03em;line-height:1.2;margin-top:5px;max-width:135mm}
.meta{text-align:right;font-size:10.5px;color:var(--muted);line-height:1.6;white-space:nowrap}
.meta b{color:var(--ink2)}
/* 판정 배지 */
.verdict{display:flex;align-items:center;gap:12px;margin:14px 0 4px;padding:12px 16px;border-radius:12px;border:1px solid var(--line)}
.verdict.go{background:var(--go-bg)} .verdict.cond{background:var(--cond-bg)} .verdict.hold{background:var(--hold-bg)}
.vlabel{font-size:10px;font-weight:700;letter-spacing:.1em;color:var(--muted)}
.vbig{font-size:17px;font-weight:800;letter-spacing:-.02em}
.verdict.go .vbig{color:var(--go)} .verdict.cond .vbig{color:var(--cond)} .verdict.hold .vbig{color:var(--hold)}
.vdot{width:11px;height:11px;border-radius:50%}
.verdict.go .vdot{background:var(--go)} .verdict.cond .vdot{background:var(--cond)} .verdict.hold .vdot{background:var(--hold)}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px 20px;margin-top:14px}
section{break-inside:avoid}
h2{font-size:12px;font-weight:800;letter-spacing:-.01em;margin-bottom:7px;padding-left:8px;border-left:3px solid var(--accent)}
table{width:100%;border-collapse:collapse;font-size:11px}
.ov th{text-align:left;color:var(--muted);font-weight:600;padding:4px 8px 4px 0;white-space:nowrap;vertical-align:top;width:66px}
.ov td{padding:4px 0;color:var(--ink2);border-bottom:1px solid var(--soft)}
.summary{font-size:11.5px;color:var(--ink2);line-height:1.6;background:var(--soft);padding:11px 13px;border-radius:9px}
ul{list-style:none;font-size:11px;color:var(--ink2)}
ul li{position:relative;padding-left:13px;margin:4px 0;line-height:1.5}
ul li:before{content:"";position:absolute;left:2px;top:7px;width:4px;height:4px;border-radius:50%;background:var(--accent)}
.sc{width:100%;border-collapse:collapse;font-size:10.5px;margin-top:2px}
.sc th{background:var(--soft);color:var(--muted);font-weight:600;text-align:left;padding:5px 8px;border-bottom:1px solid var(--line)}
.sc td{padding:5px 8px;border-bottom:1px solid var(--soft);color:var(--ink2)}
.sc td.pt{text-align:right;font-weight:700;color:var(--ink)}
.sc tr.hi td{background:#FCF1EC}
.sc tr.hi td:first-child{font-weight:700;color:var(--ink)}
.note{font-size:10px;color:var(--muted);margin-top:5px;line-height:1.5}
.two{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.foot{margin-top:16px;border-top:1px solid var(--line);padding-top:8px;font-size:9.5px;color:var(--muted);line-height:1.5}
@media print{body{background:#fff;padding:0}.page{box-shadow:none;margin:0}@page{size:A4;margin:0}}
</style></head><body>
<div class="page">
 <div class="top">
   <div><div class="eyebrow">과업분석보고서 · 수주 판단</div><h1>{{TITLE}}</h1></div>
   <div class="meta">공고번호 <b>{{NO}}</b><br>기초금액 <b>{{AMT}}</b><br>마감 <b>{{DDAY}}</b><br>{{GEN}}</div>
 </div>

 <div class="verdict {{VCLASS}}">
   <span class="vdot"></span>
   <div><div class="vlabel">적합도 판정</div><div class="vbig">{{VERDICT}}</div></div>
 </div>

 <div class="grid">
   <section><h2>공고 개요</h2><table class="ov">{{OVERVIEW}}</table></section>
   <section><h2>과업 정의</h2>
     <div class="summary">{{SUMMARY}}</div>
     <ul style="margin-top:8px">{{SCOPE}}</ul>
   </section>
 </div>

 <section style="margin-top:16px"><h2>평가 배점 (승부처)</h2>
   <table class="sc"><thead><tr><th>구분</th><th>평가항목</th><th style="text-align:right">배점</th></tr></thead>
   <tbody>{{SCORING}}</tbody></table>
   <div class="note">{{SCORENOTE}}</div>
 </section>

 <div class="two" style="margin-top:16px">
   <section><h2>참가자격 · 실적 요건</h2><ul>{{QUAL}}</ul></section>
   <section><h2>핵심 일정</h2><table class="ov">{{SCHED}}</table></section>
 </div>

 <div class="two" style="margin-top:16px">
   <section><h2>붙어야 하는 이유</h2><ul>{{REASONS}}</ul></section>
   <section><h2>리스크 · 확인사항</h2><ul>{{RISKS}}</ul></section>
 </div>

 <div class="foot">{{SRC}}</div>
</div></body></html>"""

if __name__ == "__main__":
    path = sys.argv[1]
    d = json.load(open(path, encoding="utf-8"))
    out = f"report_{d['no']}.html"
    open(out, "w", encoding="utf-8").write(build(d))
    print("생성:", out, "·", d["name"])
