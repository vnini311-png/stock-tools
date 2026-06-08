#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_revenue.py — 抓取公開資訊觀測站 (MOPS) 月營收彙總表，清理後輸出成 data/ 下的 JSON。

風格沿用 build_macd.py：
  - 民國年/西元年自動轉換
  - pretty-print JSON（方便 git diff 逐欄位看）
  - 寫到 ./data/ 目錄，HTML 用 fetch 讀取
  - 紅漲綠跌由前端 CSS 處理，這裡只給數值

用法：
  python3 build_revenue.py                 # 抓「上個月」上市+上櫃
  python3 build_revenue.py 2026 5          # 指定西元年月
  python3 build_revenue.py 2026 5 sii      # 只抓上市

輸出：
  data/monthly_revenue_2026_05.json
"""

import sys
import json
import time
import datetime
from io import StringIO
from pathlib import Path

import requests
import pandas as pd

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
MARKETS = {
    "sii": "上市",
    "otc": "上櫃",
    "rotc": "興櫃",
}
DATA_DIR = Path("./data")


def to_number(x):
    """把 '1,234' / '1,234.5' / '-' / 'NaN' 轉成 float 或 None。"""
    if x is None:
        return None
    s = str(x).strip().replace(",", "").replace("　", "")
    if s in ("", "-", "--", "不適用", "nan", "NaN"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def fetch_market(year, month, market):
    """抓單一市場單月的營收彙總表，回傳清理後的 list[dict]。"""
    roc = year - 1911 if year > 1911 else year
    url = f"https://mops.twse.com.tw/nas/t21/{market}/t21sc03_{roc}_{month}_0.html"

    r = requests.get(url, headers=HEADERS, timeout=30)
    r.encoding = "big5"  # MOPS 是 big5
    r.raise_for_status()

    # MOPS 一頁多個表格（每個產業一塊），read_html 全抓回來
    tables = pd.read_html(StringIO(r.text))

    rows = []
    for tbl in tables:
        # 營收表格通常 >= 10 欄；產業標題列等雜訊表格欄數較少，略過
        if tbl.shape[1] < 10:
            continue
        # 攤平多層欄名
        tbl.columns = [
            "".join(str(c) for c in col) if isinstance(col, tuple) else str(col)
            for col in tbl.columns
        ]

        for _, row in tbl.iterrows():
            vals = list(row.values)
            code = str(vals[0]).strip()
            # 過濾掉小計/標題/說明列：第一欄不是 4 位數字就跳過
            if not (code.isdigit() and len(code) == 4):
                continue

            rows.append({
                "code": code,
                "name": str(vals[1]).strip(),
                "revenue": to_number(vals[2]),          # 當月營收(仟元)
                "revenue_last_month": to_number(vals[3]),  # 上月營收
                "revenue_last_year": to_number(vals[4]),   # 去年當月
                "mom": to_number(vals[5]),              # 月增率(%)
                "yoy": to_number(vals[6]),              # 年增率(%)
                "cum_revenue": to_number(vals[7]),      # 當月累計
                "cum_revenue_last_year": to_number(vals[8]),  # 去年累計
                "cum_yoy": to_number(vals[9]),          # 前期比較增減(%)
                "market": MARKETS.get(market, market),
            })
    return rows


def build(year, month, markets):
    DATA_DIR.mkdir(exist_ok=True)
    all_rows = []
    for i, mkt in enumerate(markets):
        if i > 0:
            time.sleep(3)  # 禮貌間隔，避免被 MOPS 擋
        try:
            rows = fetch_market(year, month, mkt)
            print(f"  {MARKETS.get(mkt, mkt)} ({mkt}): {len(rows)} 檔")
            all_rows.extend(rows)
        except Exception as e:
            print(f"  [警告] {mkt} 抓取失敗：{e}")

    # 依年增率排序（高到低，None 排最後）
    all_rows.sort(key=lambda r: (r["yoy"] is None, -(r["yoy"] or 0)))

    payload = {
        "year": year,
        "month": month,
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "count": len(all_rows),
        "unit": "仟元",
        "data": all_rows,
    }

    out = DATA_DIR / f"monthly_revenue_{year}_{month:02d}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"\n已輸出 {out}（共 {len(all_rows)} 檔）")
    return out


def main():
    args = sys.argv[1:]

    # 預設抓「上個月」
    today = datetime.date.today()
    first = today.replace(day=1)
    last_month = first - datetime.timedelta(days=1)
    year, month = last_month.year, last_month.month
    markets = ["sii", "otc"]

    if len(args) >= 2:
        year, month = int(args[0]), int(args[1])
    if len(args) >= 3:
        markets = [args[2]]

    print(f"抓取 {year} 年 {month} 月營收（{', '.join(markets)}）...")
    build(year, month, markets)


if __name__ == "__main__":
    main()
