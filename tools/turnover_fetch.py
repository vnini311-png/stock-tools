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
  python3 turnover_fetch.py --us --push      # 更新美股：Nasdaq 清單+Yahoo 歷史，近 6 個已收盤日整段重建

美股口徑：收盤價×成交量（dollar volume 標準算法），候選池 = 當日成交值前 1000 + 市值前 300（不含 ETF）。

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

# ---------- 美股 ----------
US_KEEP_DAYS = 6
US_NAME_MAP = {
    "MU": "美光科技", "NVDA": "輝達", "TSLA": "特斯拉", "INTC": "英特爾",
    "AMD": "超微半導體", "MSFT": "微軟", "AMZN": "亞馬遜", "MRVL": "邁威爾科技",
    "AAPL": "蘋果", "AVGO": "博通", "GOOGL": "Alphabet", "GOOG": "Alphabet",
    "META": "Meta", "ARM": "安謀控股", "ORCL": "甲骨文", "ADBE": "Adobe",
    "ASML": "艾司摩爾", "AMAT": "應用材料", "WDC": "Western Digital",
    "STX": "希捷", "SNDK": "SanDisk", "PLTR": "Palantir", "LRCX": "科林研發",
    "KLAC": "科磊", "LITE": "Lumentum", "COHR": "Coherent", "NFLX": "Netflix",
    "TSM": "台積電ADR", "HOOD": "Robinhood", "NBIS": "Nebius", "SMCI": "美超微",
    "DELL": "戴爾", "VRT": "Vertiv", "QCOM": "高通", "TXN": "德州儀器",
    "COIN": "Coinbase", "MSTR": "Strategy", "CRWD": "CrowdStrike", "IBM": "IBM",
    "RKLB": "Rocket Lab", "SATS": "EchoStar", "ANET": "Arista", "CLS": "Celestica",
    "CRDO": "Credo", "ALAB": "Astera Labs", "UNH": "聯合健康", "LLY": "禮來",
    "JPM": "摩根大通", "XOM": "埃克森美孚", "WMT": "沃爾瑪", "COST": "好市多",
    "V": "Visa", "MA": "萬事達", "BAC": "美國銀行", "CRM": "Salesforce",
    "UBER": "優步", "BA": "波音", "DIS": "迪士尼", "GE": "奇異", "CAT": "開拓重工",
    "VST": "Vistra", "CEG": "Constellation", "OKLO": "Oklo", "APP": "AppLovin",
    "SPCX": "SpaceX",
}
US_INDUSTRY_MAP = {
    "MU": "記憶體", "WDC": "記憶體", "STX": "記憶體", "SNDK": "記憶體",
    "NVDA": "GPU/CPU", "AMD": "GPU/CPU", "INTC": "半導體", "AVGO": "半導體",
    "MRVL": "半導體", "QCOM": "半導體", "TXN": "半導體", "TSM": "半導體",
    "ASML": "半導體設備", "AMAT": "半導體設備", "LRCX": "半導體設備", "KLAC": "半導體設備",
    "ARM": "矽智財", "AAPL": "終端裝置", "MSFT": "M7、AI雲端", "AMZN": "M7、AI雲端",
    "GOOGL": "M7、AI雲端", "GOOG": "M7、AI雲端", "META": "M7、AI雲端",
    "TSLA": "電動車", "NFLX": "串流", "ORCL": "AI雲端", "NBIS": "AI雲端",
    "PLTR": "國防 AI", "HOOD": "券商", "COIN": "加密貨幣", "MSTR": "加密貨幣",
    "LITE": "光通訊", "COHR": "光通訊", "ANET": "網通", "CLS": "AI硬體",
    "CRDO": "AI硬體", "ALAB": "AI硬體", "SMCI": "AI伺服器", "DELL": "AI伺服器",
    "VRT": "電源/散熱", "CRWD": "資安", "IBM": "軟體", "ADBE": "軟體", "CRM": "軟體",
    "VST": "電力", "CEG": "電力", "OKLO": "電力", "RKLB": "太空", "SPCX": "太空",
    "SATS": "通訊",
    "UNH": "醫療保險", "LLY": "製藥", "JPM": "金融", "BAC": "金融",
    "V": "支付", "MA": "支付", "XOM": "能源", "WMT": "零售", "COST": "零售",
    "UBER": "平台", "BA": "航太", "DIS": "媒體", "APP": "軟體",
}
US_SECTOR_ZH = {
    "Technology": "科技", "Consumer Discretionary": "消費", "Health Care": "醫療",
    "Finance": "金融", "Financial Services": "金融", "Industrials": "工業",
    "Energy": "能源", "Telecommunications": "通訊", "Consumer Staples": "必需消費",
    "Utilities": "公用事業", "Basic Materials": "原物料", "Real Estate": "不動產",
}


def fetch_us_screener():
    """Nasdaq 股票 screener（不含 ETF），回傳 {symbol: (今日成交值億USD, 市值, sector, 簡名)}。"""
    d = fetch_json("https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=25&offset=0&download=true")
    out = {}
    for r in d["data"]["rows"]:
        try:
            price = float(r["lastsale"].replace("$", "").replace(",", ""))
            vol = float((r["volume"] or "0").replace(",", ""))
            mcap = float((r["marketCap"] or "0").replace(",", ""))
        except (ValueError, AttributeError):
            continue
        name = re.split(r" Common| Class | American Depositary| Ordinary", r["name"])[0]
        name = re.sub(r"[,.]? (Inc|Corp|Corporation|Ltd|plc|Co)\.?$", "", name).strip()
        out[r["symbol"]] = (price * vol / 1e8, mcap, r.get("sector") or "", name)
    return out


def fetch_us_daily():
    """近 6 個已收盤交易日的美股成交值 Top 20（收盤價×成交量，億 USD）。"""
    import warnings
    warnings.filterwarnings("ignore")
    import yfinance as yf
    from zoneinfo import ZoneInfo

    scr = fetch_us_screener()
    by_dv = sorted(scr, key=lambda s: -scr[s][0])[:1000]
    by_mc = sorted(scr, key=lambda s: -scr[s][1])[:300]
    uni = sorted({s.replace("/", "-") for s in by_dv} | {s.replace("/", "-") for s in by_mc})
    print(f"候選池 {len(uni)} 檔，抓取近 12 日歷史（約 1-2 分鐘）...")
    df = yf.download(uni, period="12d", interval="1d", group_by="column",
                     threads=True, progress=False, auto_adjust=False)
    dv = (df["Close"] * df["Volume"] / 1e8).dropna(how="all")

    now_ny = datetime.datetime.now(ZoneInfo("America/New_York"))
    if len(dv) and dv.index[-1].date() == now_ny.date() and now_ny.hour < 16:
        dv = dv.iloc[:-1]  # 今天美股尚未收盤，剔除盤中不完整資料

    daily = {}
    for ts in dv.index[-US_KEEP_DAYS:]:
        row = dv.loc[ts].dropna().sort_values(ascending=False).head(TOP_N)
        entry = []
        for sym, val in row.items():
            key = sym.replace("-", "/")
            info = scr.get(key) or scr.get(sym) or (0, 0, "", sym)
            name = US_NAME_MAP.get(sym) or info[3] or sym
            ind = US_INDUSTRY_MAP.get(sym) or US_SECTOR_ZH.get(info[2], "其他")
            entry.append([name, sym, ind, round(float(val), 1)])
        daily[ts.strftime("%Y/%m/%d")] = entry
    return daily



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


def parse_daily(html, var, end_anchor):
    m = re.search(rf"const {var}=({{.*?}});\s*\n{end_anchor}", html, re.S)
    if not m:
        sys.exit(f"找不到 {var} 區塊，HTML 結構可能變了")
    literal = re.sub(r",\s*([}\]])", r"\1", m.group(1))
    return json.loads(literal), m.span(1)


def parse_tw_daily(html):
    return parse_daily(html, "TW_DAILY", "const US_DAILY=")


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


def do_push(msg):
    def git(*args, check=True):
        r = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True)
        if check and r.returncode != 0:
            sys.exit(f"git {' '.join(args)} 失敗：{r.stderr.strip()}")
        return r
    git("add", str(HTML.relative_to(REPO)))
    c = git("commit", "-m", msg, check=False)
    if c.returncode != 0:
        print("git commit：沒有變更，跳過 push")
        return
    git("pull", "--rebase")
    git("push")
    print("已 push 至 GitHub Pages")


def run_us(a):
    daily = fetch_us_daily()
    days = sorted(daily)
    print(f"=== 美股成交值 Top {TOP_N}（收盤×成交量，億 USD）最新日 {days[-1]} ===")
    for i, (n, c, ind, amt) in enumerate(daily[days[-1]], 1):
        print(f"{i:2d} {n:16s} {c:6s} {ind:10s} {amt:8.1f}")
    if a.dry_run:
        return
    html = HTML.read_text(encoding="utf-8")
    _, span = parse_daily(html, "US_DAILY", "const PALETTE")
    html = html[:span[0]] + fmt_tw_daily(daily) + html[span[1]:]
    short = lambda d: f"{int(d[5:7])}/{d[8:]}"
    html = re.sub(r"美股 \d{4}/\d{2}/\d{2}", f"美股 {days[-1]}", html, count=1)
    html = re.sub(r"美股 \d+/\d+→\d+/\d+（\d+ 日）",
                  f"美股 {short(days[0])}→{short(days[-1])}（{len(days)} 日）", html, count=1)
    html = re.sub(r"美股基準 \d{4}-\d{2}-\d{2}", f"美股基準 {days[0].replace('/', '-')}", html, count=1)
    HTML.write_text(html, encoding="utf-8")
    print(f"\n已寫入 {HTML.name}：美股 {days[0]} → {days[-1]}（{len(days)} 日，整段重建）")
    if a.push:
        do_push(f"Update turnover ranking: US through {days[-1]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYYMMDD，預設今天（台股模式）")
    ap.add_argument("--us", action="store_true", help="更新美股（近 6 個已收盤交易日，整段重建）")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--push", action="store_true")
    a = ap.parse_args()
    if a.us:
        return run_us(a)
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
        do_push(f"Update turnover ranking: TW {day_key}")


if __name__ == "__main__":
    main()
