#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
g2b_rfp.py — 나라장터 공고의 제안요청서(RFP) 판별 + 통합 텍스트 추출 모듈
- 판별: 첨부에 제안요청서/과업지시서가 API로 들어오는지 분류
  · RFP_API      : 제안요청서/과업지시서 파일이 API 첨부에 존재 → 자동 추출 가능
  · NOTICE_ONLY  : 입찰공고서/공고문만 존재 → 실질 RFP는 별도 규격서 → 브라우저 분기
  · NONE         : 첨부 없음 → 방문수령/전화 분기
- 추출: PDF(pdfplumber) / HWP(olefile) / HWPX(zip+xml) 통합 dispatch
사용(단독): SERVICE_KEY=키 python3 g2b_rfp.py "<공고명키워드>" [공고번호]
"""
import os, sys, io, re, json, zipfile, struct, urllib.parse, requests

BASE = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServcPPSSrch"
RFP_KW    = ["제안요청서", "과업지시서", "과업내용서", "과업설명서", "제안안내서", "과업지침"]
NOTICE_KW = ["입찰공고", "공고문", "공고서", "재공고", "설명서"]

# ---------- 첨부 판별 ----------
def attachments_of(item):
    out = []
    for i in range(1, 11):
        n = item.get("ntceSpecFileNm%d" % i)
        u = item.get("ntceSpecDocUrl%d" % i)
        if u:
            out.append((n or "", u))
    return out

def rfp_status(item):
    atts = attachments_of(item)
    rfp    = [(n, u) for n, u in atts if any(k in n for k in RFP_KW)]
    notice = [(n, u) for n, u in atts if any(k in n for k in NOTICE_KW) and (n, u) not in rfp]
    if rfp:
        return "RFP_API", rfp, notice
    if atts or item.get("stdNtceDocUrl"):
        return "NOTICE_ONLY", [], notice
    return "NONE", [], []

def branch_hint(item, status):
    url = item.get("bidNtceDtlUrl") or item.get("bidNtceUrl") or ""
    if status == "RFP_API":
        return "자동추출가능"
    if status == "NOTICE_ONLY":
        return f"규격서별도 → 브라우저: {url}"
    return f"첨부없음(방문/전화) → 담당 {item.get('ntceInsttOfclNm','')} {item.get('ntceInsttOfclTelNo','')}"

# ---------- 텍스트 추출 dispatch ----------
def extract_pdf(b):
    import pdfplumber
    t = []
    with pdfplumber.open(io.BytesIO(b)) as pdf:
        for p in pdf.pages:
            t.append(p.extract_text() or "")
    return "\n".join(t)

def extract_hwp(b):
    import olefile
    import zlib
    f = olefile.OleFileIO(io.BytesIO(b))
    comp = bool(f.openstream("FileHeader").read()[36] & 1)
    out = []
    for s in f.listdir():
        if s[0] == "BodyText":
            data = f.openstream(s).read()
            if comp:
                data = zlib.decompress(data, -15)
            i = 0
            while i < len(data):
                h = struct.unpack("<I", data[i:i+4])[0]; tag = h & 0x3ff; size = (h >> 20) & 0xfff; i += 4
                if tag == 67:
                    txt = data[i:i+size].decode("utf-16le", "ignore")
                    txt = "".join(c for c in txt if ord(c) >= 32 or c in "\n\t")
                    if re.search(r"[가-힣0-9]", txt):
                        out.append(re.sub(r"[㐀-䶿一-鿿]{2,}", "", txt).strip())
                i += size
    return "\n".join(x for x in out if x)

def extract_hwpx(b):
    z = zipfile.ZipFile(io.BytesIO(b))
    secs = sorted(n for n in z.namelist() if "section" in n.lower() and n.endswith(".xml"))
    out = []
    for n in secs:
        xml = z.read(n).decode("utf-8", "ignore")
        for t in re.findall(r"<hp:t>(.*?)</hp:t>", xml, re.S):
            t = re.sub(r"<[^>]+>", "", t)
            t = t.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&").replace("&quot;", '"')
            if t.strip():
                out.append(t)
    return "\n".join(out)

def extract_text(name, content):
    ext = name.lower().rsplit(".", 1)[-1]
    if ext == "pdf":  return extract_pdf(content)
    if ext == "hwpx": return extract_hwpx(content)
    if ext == "hwp":  return extract_hwp(content)
    raise ValueError("지원 안 함: " + ext)

# ---------- 통합: 공고번호 → RFP 텍스트 ----------
def find_by_name(keyword, key, no=None, days=30):
    """공고명 키워드로 빠르게 조회(bidNtceNm 검색). no 주어지면 그걸로 확정."""
    import datetime
    end = datetime.datetime.now(); start = end - datetime.timedelta(days=days)
    p = {"serviceKey": key, "inqryDiv": "1",
         "inqryBgnDt": start.strftime("%Y%m%d") + "0000",
         "inqryEndDt": end.strftime("%Y%m%d") + "2359",
         "pageNo": "1", "numOfRows": "999", "type": "json", "bidNtceNm": keyword}
    r = requests.get(BASE + "?" + urllib.parse.urlencode(p), timeout=90)
    items = json.loads(r.text).get("response", {}).get("body", {}).get("items", [])
    if isinstance(items, dict): items = items.get("item", [])
    if no:
        for it in items:
            if it.get("bidNtceNo") == no:
                return it
    return items[0] if items else None

def get_rfp_text(item, key):
    status, rfp, notice = rfp_status(item)
    if status != "RFP_API":
        return {"status": status, "branch": branch_hint(item, status), "text": None}
    chunks = []
    for n, u in rfp:
        try:
            b = requests.get(u, timeout=120).content
            chunks.append(f"\n===== {n} =====\n" + extract_text(n, b))
        except Exception as e:
            chunks.append(f"[{n} 추출실패: {e}]")
    return {"status": status, "branch": "자동추출가능", "text": "\n".join(chunks), "files": [n for n, _ in rfp]}

if __name__ == "__main__":
    key = os.environ.get("SERVICE_KEY", "").strip()
    kw = sys.argv[1] if len(sys.argv) > 1 else ""
    no = sys.argv[2] if len(sys.argv) > 2 else None
    if not key or not kw:
        print('사용: SERVICE_KEY=키 python3 g2b_rfp.py "<공고명키워드>" [공고번호]'); sys.exit(1)
    it = find_by_name(kw, key, no)
    if not it:
        print("공고 없음:", kw); sys.exit(1)
    print("공고:", it.get("bidNtceNm"))
    res = get_rfp_text(it, key)
    print("RFP상태:", res["status"], "|", res["branch"])
    if res.get("text"):
        print("추출 글자수:", len(res["text"]))
        print(res["text"][:600])
