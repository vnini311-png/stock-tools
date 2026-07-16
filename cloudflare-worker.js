/**
 * 元大自選股 — 即時報價中繼 (Cloudflare Worker)
 *
 * 2026-07 架構調整：TWSE MIS 已封鎖 Cloudflare 出口 IP，Worker 無法直接抓報價。
 * 改為「本機推送」模式：
 *   - 家中 Mac 執行 quote_pusher.py，盤中每 20 秒從 TWSE MIS 抓好報價，
 *     POST /api/push（帶 X-Push-Key 驗證）寫入 KV。
 *   - 網頁照舊 GET /api/quote?codes=2330,2454,... 讀取，介面與舊版完全相容。
 *
 * 部署需求（Cloudflare Dashboard）：
 *   1. KV namespace 綁定：變數名 QUOTES
 *   2. Secret：PUSH_KEY（與 quote_pusher.py 內的 PUSH_KEY 相同）
 */

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, X-Push-Key",
};

// KV 內容超過此秒數視為過時（僅影響 stale 標記，仍照樣回傳）
const STALE_SECS = 120;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS });
    }

    if (url.pathname.endsWith("/api/push") && request.method === "POST") {
      return handlePush(request, env);
    }
    if (url.pathname.endsWith("/api/quote")) {
      return handleQuote(url, env);
    }
    return json({ error: "not found" }, 404);
  },
};

async function handlePush(request, env) {
  const key = request.headers.get("X-Push-Key") || "";
  if (!env.PUSH_KEY || key !== env.PUSH_KEY) {
    return json({ error: "unauthorized" }, 401);
  }
  let body;
  try {
    body = await request.json();
  } catch (e) {
    return json({ error: "bad json" }, 400);
  }
  if (!body || typeof body.quotes !== "object") {
    return json({ error: "missing quotes" }, 400);
  }
  const record = {
    quotes: body.quotes,
    pushedAt: Math.floor(Date.now() / 1000),
  };
  await env.QUOTES.put("latest", JSON.stringify(record));
  return json({ ok: true, count: Object.keys(body.quotes).length });
}

async function handleQuote(url, env) {
  const codes = (url.searchParams.get("codes") || "")
    .split(",").map((s) => s.trim()).filter(Boolean);
  if (!codes.length) return json({ error: "no codes provided" }, 400);

  let record = null;
  try {
    const raw = await env.QUOTES.get("latest");
    if (raw) record = JSON.parse(raw);
  } catch (e) { /* treat as empty */ }

  const all = (record && record.quotes) || {};
  const quotes = {};
  for (const c of codes) if (all[c]) quotes[c] = all[c];

  const pushedAt = record ? record.pushedAt : 0;
  const now = Math.floor(Date.now() / 1000);
  return json({
    quotes,
    requested: codes,
    missing: codes.filter((c) => !quotes[c]),
    fetchedAt: pushedAt || now,
    stale: !pushedAt || now - pushedAt > STALE_SECS,
  });
}

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { ...CORS, "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
  });
}
