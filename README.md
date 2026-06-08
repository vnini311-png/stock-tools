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
