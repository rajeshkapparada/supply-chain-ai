const BASE = "http://localhost:5000";

async function parseJSON(res) {
  const text = await res.text();
  try {
    return text ? JSON.parse(text) : {};
  } catch {
    return { error: text || "Invalid JSON response" };
  }
}

export async function getJSON(path) {
  const res = await fetch(`${BASE}${path}`);
  const data = await parseJSON(res);
  if (!res.ok) throw new Error(data?.error || "Request failed");
  return data;
}

export async function postJSON(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  const data = await parseJSON(res);
  if (!res.ok) throw new Error(data?.error || "Request failed");
  return data;
}

export async function runForecast(horizon = 7) {
  return postJSON(`/forecast/run?horizon=${horizon}`, {});
}

export async function runMcp(run_id, horizon_days = 14) {
  return postJSON(`/inventory/mcp/run`, { run_id, horizon_days });
}

export async function getMcpHistory(limit = 200) {
  return getJSON(`/inventory/mcp/history?limit=${limit}`);
}

export async function getInventorySnapshot(limit = 50) {
  return getJSON(`/analytics/inventory_snapshot?limit=${limit}`);
}

export async function getSupplierScores() {
  return getJSON(`/suppliers/score`);
}

export async function getDemandByRegion() {
  return getJSON(`/analytics/demand_by_region`);
}

export async function getPromoEvents(limit = 200) {
  return getJSON(`/analytics/promo_events?limit=${limit}`);
}

export async function getAnalyticsSummary() {
  return getJSON(`/analytics/summary`);
}

export async function getDailyDemand() {
  return getJSON(`/analytics/daily_demand`);
}

export async function getTopSkus(n = 10) {
  return getJSON(`/analytics/top_skus?n=${n}`);
}
