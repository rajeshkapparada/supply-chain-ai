import { useEffect, useMemo, useState } from "react";
import { getMcpHistory, runForecast, runMcp } from "../services/api";

export default function Feature2Inventory() {
  const [forecastDays, setForecastDays] = useState(7);
  const [mcpDays, setMcpDays] = useState(14);
  const [runId, setRunId] = useState(null);
  const [latestRows, setLatestRows] = useState([]);
  const [historyRows, setHistoryRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    loadHistory();
  }, []);

  async function loadHistory() {
    try {
      const data = await getMcpHistory(200);
      setHistoryRows(data.rows || []);
    } catch {
      setHistoryRows([]);
    }
  }

  async function runPipeline() {
    setError("");
    setLoading(true);
    try {
      const f = await runForecast(Math.max(1, Math.min(Number(forecastDays || 7), 30)));
      const newRunId = f?.meta?.run_id;
      if (!newRunId) throw new Error("Forecast did not return run_id");

      setRunId(newRunId);

      const m = await runMcp(newRunId, Math.max(1, Math.min(Number(mcpDays || 14), 30)));
      setLatestRows(m.items || []);

      await loadHistory();
    } catch (e) {
      setError(e.message || "Failed to run inventory pipeline");
    } finally {
      setLoading(false);
    }
  }

  const summary = useMemo(() => {
    if (!latestRows.length) return null;
    return {
      total: latestRows.length,
      reorder: latestRows.filter((r) => r.recommendedAction === "REORDER").length,
      low: latestRows.filter((r) => r.status === "LOW").length,
      out: latestRows.filter((r) => r.status === "OUT").length,
    };
  }, [latestRows]);

  return (
    <div>
      <h1>Feature 2: Inventory Monitoring</h1>
      <p className="small-muted">Inventory agent runs the latest forecast first, then uses that forecast to calculate reorder decisions.</p>

      <div className="page-card">
        <div className="input-row">
          <div className="input-box">
            <label>Forecast days</label>
            <input type="number" min="1" max="30" value={forecastDays} onChange={(e) => setForecastDays(e.target.value)} />
          </div>
          <div className="input-box">
            <label>Simulation days</label>
            <input type="number" min="1" max="30" value={mcpDays} onChange={(e) => setMcpDays(e.target.value)} />
          </div>
          <button className="btn" onClick={runPipeline} disabled={loading}>{loading ? "Running..." : "Run Inventory Reorder"}</button>
        </div>

        {runId && <div className="small-muted" style={{ marginTop: 8 }}>Current run generated reorder decisions from the latest forecast output.</div>}
        {error && <div className="error">{error}</div>}
      </div>

      {summary && (
        <div className="kpi-grid">
          <Kpi label="Total rows" value={summary.total} />
          <Kpi label="Reorder decisions" value={summary.reorder} />
          <Kpi label="Low stock" value={summary.low} />
          <Kpi label="Out of stock" value={summary.out} />
        </div>
      )}

      <div className="page-card">
        <h3>Current Reorder Decisions</h3>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Day</th>
                <th>SKU</th>
                <th>WH</th>
                <th>Inventory</th>
                <th>ROP</th>
                <th>Demand</th>
                <th>Action</th>
                <th>Qty</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {latestRows.map((r, i) => (
                <tr key={i}>
                  <td>{r.day}</td>
                  <td>{r.sku}</td>
                  <td>{r.warehouse}</td>
                  <td>{r.inventory}</td>
                  <td>{r.reorderPoint}</td>
                  <td>{r.dailyDemand}</td>
                  <td>{r.recommendedAction}</td>
                  <td>{r.recommendedQty}</td>
                  <td>{r.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="page-card">
        <h3>Reorder Decision History</h3>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Created</th>
                <th>Run</th>
                <th>Day</th>
                <th>SKU</th>
                <th>WH</th>
                <th>Action</th>
                <th>Qty</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {historyRows.map((r, i) => (
                <tr key={i}>
                  <td>{r.created_at}</td>
                  <td>{r.run_id}</td>
                  <td>{r.day}</td>
                  <td>{r.sku}</td>
                  <td>{r.warehouse}</td>
                  <td>{r.recommended_action}</td>
                  <td>{r.recommended_qty}</td>
                  <td>{r.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function Kpi({ label, value }) {
  return (
    <div className="kpi-box">
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
    </div>
  );
}
