/**
 * 元大自選股 — 即時報價代理 (Cloudflare Worker)
 *
 * 提供 GET /api/quote?codes=2330,2454,...
 * 從證交所 MIS (mis.twse.com.tw) 抓近即時報價，繞過瀏覽器 CORS，
 * 邏輯對齊本機的 server.py：自動分批、z 缺失時用買賣中價/漲跌停估價。
 *
 * 部署：
 *   1. https://dash.cloudflare.com → Workers & Pages → Create Worker
 *   2. 把本檔內容貼上、Deploy，記下網址（例如 https://xxx.your-name.workers.dev）
 *   3. 在 build_html.py 把 QUOTE_WORKER_URL 改成  <你的網址>/api/quote  後重建 HTML
 *
 * 也可用 wrangler：wrangler deploy cloudflare-worker.js
 */

const MIS = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp";
const LANDING = "https://mis.twse.com.tw/stock/index.jsp";
const BATCH = 40; // 每批檔數（每檔 2 頻道 tse_/otc_，避免 URL 過長 414）

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS });
    }
    if (!url.pathname.endsWith("/api/quote")) {
      return json({ error: "not found" }, 404);
    }
    const codes = (url.searchParams.get("codes") || "")
      .split(",").map((s) => s.trim()).filter(Boolean);
    if (!codes.length) return json({ error: "no codes provided" }, 400);

    try {
      const cookie = await getCookie();
      const quotes = {};
      for (let i = 0; i < codes.length; i += BATCH) {
        const chunk = codes.slice(i, i + BATCH);
        const parts = [];
        for (const c of chunk) { parts.push(`tse_${c}.tw`); parts.push(`otc_${c}.tw`); }
        const ex = encodeURIComponent(parts.join("|"));
        const u = `${MIS}?ex_ch=${ex}&json=1&delay=0&_=${Date.now()}`;
        try {
          const r = await fetch(u, { headers: misHeaders(cookie) });
          if (!r.ok) continue;
          const data = await r.json();
          mergeQuotes(quotes, data);
        } catch (e) { /* skip failed batch */ }
      }
      return json({
        quotes,
        requested: codes,
        missing: codes.filter((c) => !quotes[c]),
        fetchedAt: Math.floor(Date.now() / 1000),
      });
    } catch (e) {
      return json({ error: String(e) }, 502);
    }
  },
};

function misHeaders(cookie) {
  const h = {
    "User-Agent":
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " +
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Referer": "https://mis.twse.com.tw/stock/index.jsp",
    "Accept": "application/json, text/plain, */*",
  };
  if (cookie) h["Cookie"] = cookie;
  return h;
}

async function getCookie() {
  try {
    const r = await fetch(LANDING, { headers: misHeaders() });
    const sc = r.headers.get("set-cookie");
    if (sc) return sc.split(";")[0];
  } catch (e) { /* best effort */ }
  return "";
}

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { ...CORS, "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
  });
}

function safeFloat(s) {
  const v = parseFloat(String(s == null ? "" : s).trim());
  return isNaN(v) ? null : v;
}

// 取買賣五檔（'_' 分隔）的第一個正值
function firstPos(s) {
  if (!s) return null;
  for (const p of String(s).split("_")) {
    const v = safeFloat(p);
    if (v && v > 0) return v;
  }
  return null;
}

// 估算最新盤中價：z 有效用 z；否則用買賣中價；鎖漲/跌停用 high/low
function currentPrice(it) {
  const z = (it.z || "").trim();
  if (z && z !== "-") {
    const v = safeFloat(z);
    if (v && v > 0) return [v, false];
  }
  const bid = firstPos(it.b), ask = firstPos(it.a);
  if (bid && ask) return [Math.round(((bid + ask) / 2) * 10000) / 10000, true];
  const h = safeFloat(it.h), l = safeFloat(it.l);
  if (bid && !ask) return [h || bid, true]; // 鎖漲停（無人賣）
  if (ask && !bid) return [l || ask, true]; // 鎖跌停（無人買）
  const o = safeFloat(it.o), y = safeFloat(it.y);
  return [o || y, true];
}

function mergeQuotes(quotes, data) {
  for (const it of (data.msgArray || [])) {
    const code = it.c || "";
    const [price, est] = currentPrice(it);
    if (!price || price <= 0) continue;
    quotes[code] = {
      price,
      estimated: est,
      name: it.n || "",
      channel: it.ch || "",
      prevClose: safeFloat(it.y),
      open: safeFloat(it.o),
      high: safeFloat(it.h),
      low: safeFloat(it.l),
      volume: safeFloat(it.v), // 累積成交量(張)
      time: it.t || "",
      tlong: it.tlong || "",
    };
  }
}
