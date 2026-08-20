# Stock Tools 持股分析工具集

整合兩套靜態 HTML 儀表板：

- **月營收年度對比儀表板** — 折線比較 2023–2026 月營收與 YoY
- **MACD 持股分析儀表板** — 上傳股價 Excel 即時計算 MACD 指標

純前端，無後端、無建置流程，可直接用 GitHub Pages 部署。

---

## 檔案結構

```
stock-tools/
├── index.html              入口頁（工具選單）
├── tools/
│   ├── monthly-revenue.html   月營收儀表板
│   └── macd.html              MACD 儀表板
└── README.md
```

---

## 本機預覽

直接用瀏覽器打開 `index.html` 即可，或用 Python 起一個本機伺服器：

```bash
cd stock-tools
python3 -m http.server 8000
# 開瀏覽器到 http://localhost:8000
```

---

## 上傳到 GitHub 並用 Pages 部署

### 1. 在 GitHub 建立新 repo

- 到 https://github.com/new
- Repository name：建議用 `stock-tools` 之類的名字
- Public 或 Private 都可（用 Pages 免費版需 Public）
- **不要**勾選 Add README（我們自己有了）

### 2. 從本機推上去

在這個資料夾下執行（把 `YOUR_USERNAME` 換成你的 GitHub 帳號）：

```bash
git init
git add .
git commit -m "Initial commit: stock tools dashboards"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/stock-tools.git
git push -u origin main
```

### 3. 啟用 GitHub Pages

1. 進到 repo 頁面 → **Settings** → 左側 **Pages**
2. **Source** 選 `Deploy from a branch`
3. **Branch** 選 `main`，資料夾選 `/ (root)`
4. **Save**

等 1–2 分鐘，網站會出現在：

```
https://YOUR_USERNAME.github.io/stock-tools/
```

---

## 後續更新

改完檔案後：

```bash
git add .
git commit -m "Update dashboards"
git push
```

GitHub Pages 會自動重新部署。

---

## 技術備註

- 使用 [Chart.js 4.x](https://www.chartjs.org/) 繪製圖表
- MACD 工具使用 [SheetJS](https://sheetjs.com/) 解析 Excel
- 所有資料處理在瀏覽器內完成，**不會**上傳到任何伺服器

---

## 持股每日 Review 筆記（tools/daily-review.html）

沿用 Numbers「2024持股每日Review」的架構：每檔股票 × 每個 review 日期一個區塊，
分成 **T** 技術面 / **I** 籌碼面 / **S** 信用交易 / **F** 基本面 / **O** 總結五段。

四個分頁：

| 分頁 | 內容 |
|---|---|
| **Strategy** | 評等、策略、收盤漲跌、策略更新日、最後 REVIEW。評等與策略可直接在表格內編輯，改動會自動蓋上策略更新日 |
| **Overview** | 本益比（手填）、MACD 柱狀值與單日變化、KD(9,3,3)、券資比 P/C % |
| **個股 Review** | 逐檔的 T/I/S/F/O 筆記時間軸，含各段的量化數值格。上方 dashboard：MACD 柱（正紅負綠）與單日變化、K 與 K−D（附黃交/死交）、YTD 高低、融資 UR、券資比、千張大戶（連續增減週數 + 近 8 週逐週增減條） |
| **大盤** | 加權指數位階（MA/MACD/KD/RSI/YTD 高低）與大盤筆記 |

- 涵蓋範圍 = 每日持股交易數據裡的個股（我的 35 檔 + Adam 5 檔）；已出場但留有筆記的個股用「已出場」篩選查看。
- **組合**分成「我的 / Adam / 觀察」。前兩者由每日持股交易數據自動判定（來自哪一份股價 xlsx），
  在個股頁的「組合」下拉可手動改成**觀察**；這個指派存在筆記檔裡，不會被每日更新蓋掉。
  左側清單有對應的篩選鈕。
- 筆記以 PBKDF2(300k) + AES-GCM 加密存在 `data/review.enc`，開頁需密碼；明文絕不進 repo。
- 量化數據由 `data/review-metrics.json` 每日自動帶入，**不加密**（純市場資料）。

### 初次建立筆記檔

1. 產生種子檔（把 Numbers 筆記轉成 JSON，此檔已被 .gitignore）。
2. **一定要在本機做**：`python3 -m http.server 8787`，開 `http://localhost:8787/tools/daily-review.html`。
   （種子檔不會 commit，所以線上版偵測不到它。）
3. 首次開啟會自動偵測 `data/review-seed.json` 並列出檔數與筆數，勾選框**預設已勾**；
   輸入自訂密碼後按「建立」即會一併匯入。
4. 按「下載加密檔」→ 把下載到的 `review.enc` 複製成 `data/review.enc` → commit + push。

**檢查有沒有匯入成功**：有匯入的 `review.enc` 約 70 KB；只有 5 KB 表示是空白檔。
即使建成空白檔也救得回來 —— 解鎖後用標題列的「匯入 JSON」按鈕補上即可（見下）。

### 事後補匯入 / 合併筆記

標題列的「**匯入 JSON**」可以在任何時候把另一份筆記 JSON 合併進來（來源可以是種子檔，
或「匯出 JSON」產生的備份）。合併規則：

- 同一天已存在的 review **不會被覆蓋**，只加入缺少的日期
- 評等／策略／標籤只在目前是空白時才補上
- 重複匯入同一份檔案不會產生重複資料

### 每日更新數據

`auto_build_push.py` 已會自動呼叫；要手動跑：

```bash
cd stock-tools && python3 tools/review_metrics.py --push
```

讀取來源：

| 來源 | 提供 |
|---|---|
| `持股歷史股價_{30檔,ADAM組合}-*.xlsx` | MA20/60/240、MACD、KD(9,3,3)、RSI(14)、YTD 高低 |
| `twse_institutional_margin.csv` | 三大法人買賣超、融資融券、融資使用率、券資比 |
| `tools/chip_tool.html` 的 dataPayload | 外資/投信/自營持股張數與比率、千張大戶 |
| TWSE `TWT93U` + TPEx `margin/sbl` | **借券賣出餘額 LS** 與當日增減（唯一需要連網的部分） |

借券兩支端點（單位皆為股，程式換算成張）：

```
https://www.twse.com.tw/rwd/zh/marginTrading/TWT93U?date=YYYYMMDD&selectType=ALL&response=json
https://www.tpex.org.tw/www/zh-tw/margin/sbl?date=YYYY/MM/DD&response=json
```

兩張表欄位相同：`[代號, 名稱, 融券×6, 借券賣出×6, 備註]`，借券當日餘額在 index 12、前日餘額在 index 8。
連網失敗只會讓 LS 留白，不影響其他欄位；加 `--no-sbl` 可完全跳過。

> **本益比是手動欄位**，在 Overview 分頁直接填。沒有自動計算是刻意的：季報頁的 EPS 對
> 有分割的個股（如寶雅 1:10）是分割前口徑，直接除股價會算出錯得離譜的倍數。

### 寫當日 Review

開頁 → 個股 → 「新增今日 Review」：T/I/S/F/O 的數字格與 T/I/S 的敘述草稿會自動填好，
只需補 **F**（基本面）與 **O**（總結）判斷。新筆記各段的數值欄：

| 段 | 欄位 | 列 |
|---|---|---|
| **T** 技術 | MACD柱 / K / D / K−D | 數值 |
| **I** 籌碼 | QFII / QDII / Trader | 數值、增減、持股% |
| **S** 信用 | 融資 / 融資UR / 融券 / P/C / LS | 數值、增減 |

T 的第一欄與 dashboard 同樣是**柱狀值**（DIF − 慢線），不是 DIF 本身。
信用交易全部集中在 S 段，I 段只留法人動向。
**融資餘額與融資使用率並列**：兩者分母不同 —— 餘額 ÷ 發行股數 = 融資占股本比率，
餘額 ÷ 融資限額 = UR，而限額是發行股數的 25%，所以 `UR = 占股本% × 4`
（已對照上櫃官方「資使用率(%)」驗證吻合）。

2024 的舊筆記各自保留當初存的欄位名與值（I 段含融資、T 段含 RSI），不受這次調整影響。編輯完按「下載加密檔」覆蓋 `data/review.enc` 再 push。

---

## 修正股價 xlsx 的分頁命名

`持股歷史股價_*.xlsx` 的分頁名格式為「代號 名稱」，但曾有一批分頁的名稱與代號對不起來
（例：4979 標成「矽格」，實際 4979 是華星光）。每日 append 是用開頭 4 碼代號比對，
**資料本身正確**，只有標籤會誤導人。檢查與修正：

```bash
cd stock-tools && python3 tools/fix_price_sheet_names.py --apply
```

權威名稱取自 `twse_institutional_margin.csv` 的「證券名稱」。TWSE 的 `*` 註記（聖暉*、國巨*）
視為同名不改，以符合站上其他頁面的慣例。改的是最新一份 xlsx，之後每日 `--2pm` 複製時會延續。
