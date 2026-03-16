import { useMemo, useState } from "react";
import "./App.css";

export default function App() {
  const [file, setFile] = useState(null);
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function runForecast() {
    setError("");
    setRows([]);
    setMeta(null);

    if (!file) {
      setError("Please select a CSV file first.");
      return;
    }

    setLoading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch("http://127.0.0.1:5000/forecast", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        // backend may return { error: "...", missing: [...], found_columns: [...] }
        const msg =
          data?.error ||
          "Forecast failed. Check backend terminal for the exact error.";
        setError(msg);
      } else {
        setRows(data.rows || []);
        setMeta(data.meta || null);
      }
    } catch {
      setError("Backend not reachable. Is Flask running on http://127.0.0.1:5000 ?");
    } finally {
      setLoading(false);
    }
  }

  // KPI calculations for 7-day output
  const kpis = useMemo(() => {
    if (!rows.length) return null;
    const preds = rows
      .map((r) => Number(r.predicted_units))
      .filter((x) => Number.isFinite(x));

    const total = preds.reduce((a, b) => a + b, 0);
    const avg = total / (preds.length || 1);
    const max = Math.max(...preds);
    const min = Math.min(...preds);

    // daily totals across all SKUs
    const byDate = {};
    for (const r of rows) {
      const d = r.forecast_date;
      const v = Number(r.predicted_units);
      if (!Number.isFinite(v)) continue;
      byDate[d] = (byDate[d] || 0) + v;
    }

    const dailyTotals = Object.entries(byDate)
      .map(([date, totalUnits]) => ({ date, totalUnits }))
      .sort((a, b) => a.date.localeCompare(b.date));

    return { avg, max, min, dailyTotals };
  }, [rows]);

  // Top 5 predicted rows (highest predicted_units)
  const top5 = useMemo(() => {
    return [...rows]
      .sort((a, b) => Number(b.predicted_units) - Number(a.predicted_units))
      .slice(0, 5);
  }, [rows]);

  return (
    <div className="page">
      <header className="header">
        <h1>Supply Chain Intelligence Dashboard</h1>
        <p className="muted">
          Feature 1: Demand Forecasting (7-day horizon) — Upload CSV and generate
          predicted <b>Units_Sold</b> per SKU.
        </p>
      </header>

      <section className="card">
        <label className="label">Upload dataset CSV</label>
        <input
          type="file"
          accept=".csv"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
        />

        <div className="row">
          <button className="btn" onClick={runForecast} disabled={!file || loading}>
            {loading ? "Forecasting..." : "Run 7-Day Forecast"}
          </button>
          {file && (
            <div className="ok">
              Selected: <b>{file.name}</b>
            </div>
          )}
        </div>

        {error && (
          <div className="error">
            <b>Error:</b> {error}
          </div>
        )}

        {meta && (
          <div className="meta">
            Forecast generated for <b>{meta.skus}</b> SKUs • Horizon:{" "}
            <b>{meta.horizon_days}</b> days • Rows: <b>{meta.rows}</b>
          </div>
        )}
      </section>

      {rows.length > 0 && (
        <>
          {/* KPI Cards */}
          <section className="kpiGrid">
            <div className="kpiCard">
              <div className="kpiTitle">SKUs Forecasted</div>
              <div className="kpiValue">{meta?.skus ?? "-"}</div>
            </div>
            <div className="kpiCard">
              <div className="kpiTitle">Avg Predicted Units</div>
              <div className="kpiValue">{kpis ? kpis.avg.toFixed(2) : "-"}</div>
            </div>
            <div className="kpiCard">
              <div className="kpiTitle">Max Predicted</div>
              <div className="kpiValue">{kpis ? kpis.max.toFixed(2) : "-"}</div>
            </div>
            <div className="kpiCard">
              <div className="kpiTitle">Min Predicted</div>
              <div className="kpiValue">{kpis ? kpis.min.toFixed(2) : "-"}</div>
            </div>
          </section>

          {/* Daily totals (simple list) */}
          {kpis?.dailyTotals?.length > 0 && (
            <section className="card">
              <h2 className="h2">Total Predicted Demand per Day (All SKUs)</h2>
              <div className="dailyGrid">
                {kpis.dailyTotals.map((d) => (
                  <div key={d.date} className="dailyCard">
                    <div className="dailyDate">{d.date}</div>
                    <div className="dailyValue">{d.totalUnits.toFixed(2)}</div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Top 5 */}
          <section className="card">
            <h2 className="h2">Top 5 Forecast Rows (Highest Demand)</h2>
            <ul className="list">
              {top5.map((r, i) => (
                <li key={i}>
                  <b>{r.SKU_ID}</b> — {r.forecast_date} —{" "}
                  {Number(r.predicted_units).toFixed(2)}
                </li>
              ))}
            </ul>
          </section>

          {/* Results Table */}
          <section className="tableWrap">
            <table>
              <thead>
                <tr>
                  <th>SKU_ID</th>
                  <th>Forecast Date</th>
                  <th>Predicted Units</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i}>
                    <td>{r.SKU_ID}</td>
                    <td>{r.forecast_date}</td>
                    <td>{Number(r.predicted_units).toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}

      <footer className="footer muted">
        Backend: <code>http://127.0.0.1:5000</code> • Frontend:{" "}
        <code>http://localhost:5173</code>
      </footer>
    </div>
  );
}
