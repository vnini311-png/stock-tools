#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓取台股（上市+上櫃）當日成交值 Top 20，寫入 turnover-ranking.html 的 TW_DAILY。

資料來源（官方，收盤後統計，含盤後鉅額交易，口徑略大於看盤 APP）：
  - 上市：TWSE MI_INDEX 每日收盤行情
  - 上櫃：TPEx dailyQuotes 上櫃股票行情

用法（收盤後跑，建議 15:00 以後）：
  python3 turnover_fetch.py                  # 抓今天，寫入 HTML
  python3 turnover_fetch.py --date 20260727  # 抓指定日期（同日期已存在則覆蓋）
  python3 turnover_fetch.py --dry-run        # 只印排行，不改檔
  python3 turnover_fetch.py --push           # 寫入後 git commit + pull --rebase + push

新股票進榜若沒有產業標籤會標「其他」並在結尾提醒，到 INDUSTRY_MAP 補一筆即可。
"""
import argparse, datetime, json, re, subprocess, sys, urllib.request
from pathlib import Path

HTML = Path(__file__).resolve().parent / "turnover-ranking.html"
REPO = HTML.parent.parent
TOP_N = 20
KEEP_DAYS = 6  # TW_DAILY 保留的交易日數（近5日動畫 + 前一日比較用）

# 代號 → 產業標籤（顯示用，沿用 APP 慣用分法；官方分類太粗不用）
INDUSTRY_MAP = {
    "2330": "半導體", "2303": "半導體", "2327": "電子零件", "2408": "記憶體",
    "2344": "記憶體", "6770": "記憶體", "2337": "記憶體", "8299": "IC設計",
    "2454": "IC設計", "3443": "IC設計", "3231": "EMS/組裝", "2317": "EMS/組裝",
    "3481": "光電", "2409": "光電", "4958": "PCB", "8046": "PCB", "3037": "PCB",
    "3189": "PCB", "2313": "PCB", "2383": "PCB材料", "6274": "PCB材料",
    "8039": "PCB材料", "8358": "電子材料", "2308": "電源/散熱", "4979": "光通訊",
    "3081": "光通訊", "3105": "化合物半導體", "6147": "封測", "3711": "封測",
    "6239": "封測", "2449": "封測", "3374": "封測", "1303": "塑膠",
    "6669": "AI伺服器", "3008": "光學鏡頭", "6139": "機電工程", "6488": "矽晶圓",
    "6182": "矽晶圓", "3042": "石英元件", "2492": "電子零件", "3026": "被動元件",
    "2412": "電信", "2881": "金融", "2882": "金融", "2891": "金融",
    "3017": "散熱", "3260": "記憶體", "2382": "AI伺服器",
    "5483": "矽晶圓", "2360": "檢測設備", "3661": "IC設計", "2379": "IC設計",
    "2357": "品牌廠", "3529": "矽智財", "7769": "半導體設備", "3665": "連接器",
    "2301": "電源/散熱", "2368": "PCB",
}

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}


def fetch_json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def is_stock(code):
    return bool(re.fullmatch(r"[1-9]\d{3}", code))  # 4碼且不含 ETF/ETN(00xx)


def fetch_twse(ymd):
    d = fetch_json(f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={ymd}&type=ALLBUT0999&response=json")
    if d.get("stat") != "OK":
        sys.exit(f"TWSE 無 {ymd} 資料（非交易日或尚未公布）: {d.get('stat')}")
    tbl = next(t for t in d["tables"] if "每日收盤行情" in t.get("title", ""))
    out = []
    for r in tbl["data"]:
        code, name = r[0].strip(), r[1].strip()
        if not is_stock(code):
            continue
        try:
            amt = float(r[4].replace(",", "")) / 1e8
        except ValueError:
            continue
        out.append((name, code, amt))
    return out


def fetch_tpex(ymd):
    roc = f"{int(ymd[:4]) - 1911}/{ymd[4:6]}/{ymd[6:]}"
    d = fetch_json(f"https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes?date={roc}&type=EW&response=json")
    if d.get("date") != ymd:
        sys.exit(f"TPEx 回傳日期 {d.get('date')} != {ymd}（非交易日或尚未公布）")
    out = []
    for r in d["tables"][0]["data"]:
        code, name = r[0].strip(), r[1].strip()
        if not is_stock(code):
            continue
        try:
            amt = float(r[9].replace(",", "")) / 1e8
        except ValueError:
            continue
        out.append((name, code, amt))
    return out


def parse_tw_daily(html):
    m = re.search(r"const TW_DAILY=({.*?});\nconst US_DAILY=", html, re.S)
    if not m:
        sys.exit("找不到 TW_DAILY 區塊，HTML 結構可能變了")
    literal = re.sub(r",\s*([}\]])", r"\1", m.group(1))
    return json.loads(literal), m.span(1)


def fmt_tw_daily(daily):
    """輸出成與原檔一致的格式：每天一段、每行 3 筆。"""
    parts = []
    for day in sorted(daily):
        rows = daily[day]
        lines = []
        for i in range(0, len(rows), 3):
            chunk = ",".join(
                f'["{n}","{c}","{ind}",{amt:g}]' for n, c, ind, amt in rows[i:i + 3]
            )
            lines.append(" " + chunk)
        parts.append(f' "{day}":[\n' + ",\n".join(lines) + "\n ]")
    return "{\n" + ",\n".join(parts) + "\n}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYYMMDD，預設今天")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--push", action="store_true")
    a = ap.parse_args()
    ymd = a.date or datetime.date.today().strftime("%Y%m%d")
    day_key = f"{ymd[:4]}/{ymd[4:6]}/{ymd[6:]}"

    rows = fetch_twse(ymd) + fetch_tpex(ymd)
    rows.sort(key=lambda x: -x[2])
    top = rows[:TOP_N]

    html = HTML.read_text(encoding="utf-8")
    daily, span = parse_tw_daily(html)

    # 產業標籤：INDUSTRY_MAP 優先，其次沿用頁面舊資料的標法
    old_label = {}
    for d in sorted(daily):
        for n, c, ind, amt in daily[d]:
            old_label[c] = ind
    unknown = []
    entry = []
    for name, code, amt in top:
        ind = INDUSTRY_MAP.get(code) or old_label.get(code)
        if not ind:
            ind, _ = "其他", unknown.append(f"{name} {code}")
        entry.append([name, code, ind, round(amt, 1)])

    print(f"=== {day_key} 成交值 Top {TOP_N}（上市+上櫃，億）===")
    for i, (n, c, ind, amt) in enumerate(entry, 1):
        print(f"{i:2d} {n:10s} {c} {ind:8s} {amt:8.1f}")
    if a.dry_run:
        return

    replaced = day_key in daily
    daily[day_key] = entry
    keep = sorted(daily)[-KEEP_DAYS:]
    dropped = [d for d in daily if d not in keep]
    daily = {d: daily[d] for d in keep}

    html = html[:span[0]] + fmt_tw_daily(daily) + html[span[1]:]
    days = sorted(daily)
    short = lambda d: f"{int(d[5:7])}/{d[8:]}"
    html = re.sub(r"台股 \d{4}/\d{2}/\d{2}", f"台股 {days[-1]}", html, count=1)
    html = re.sub(r"台股 \d+/\d+→\d+/\d+（\d+ 日）",
                  f"台股 {short(days[0])}→{short(days[-1])}（{len(days)} 日）", html, count=1)
    html = re.sub(r"台股基準 \d{4}-\d{2}-\d{2}", f"台股基準 {days[0].replace('/', '-')}", html, count=1)
    HTML.write_text(html, encoding="utf-8")
    print(f"\n已寫入 {HTML.name}：{'覆蓋' if replaced else '新增'} {day_key}"
          + (f"，移除舊快照 {', '.join(sorted(dropped))}" if dropped else ""))
    if unknown:
        print("⚠ 以下股票無產業標籤（已標「其他」），請補進 INDUSTRY_MAP：", "、".join(unknown))

    if a.push:
        def git(*args, check=True):
            r = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True)
            if check and r.returncode != 0:
                sys.exit(f"git {' '.join(args)} 失敗：{r.stderr.strip()}")
            return r
        git("add", str(HTML.relative_to(REPO)))
        c = git("commit", "-m", f"Update turnover ranking: TW {day_key}", check=False)
        if c.returncode != 0:
            print("git commit：沒有變更，跳過 push")
            return
        git("pull", "--rebase")
        git("push")
        print("已 push 至 GitHub Pages")


if __name__ == "__main__":
    main()
