import { useMemo, useState } from "react";
import Plot from "react-plotly.js";
import { runForecast } from "../services/api";

export default function Feature1Forecast() {
  const [days, setDays] = useState(7);
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function onRunForecast() {
    setError("");
    setLoading(true);
    try {
      const safeDays = Math.max(1, Math.min(Number(days || 7), 30));
      const data = await runForecast(safeDays);
      setRows(data.rows || []);
      setMeta(data.meta || null);
    } catch (e) {
      setError(e.message || "Forecast failed");
      setRows([]);
      setMeta(null);
    } finally {
      setLoading(false);
    }
  }

  const kpis = useMemo(() => {
    if (!rows.length) return null;
    const vals = rows.map((r) => Number(r.predicted_units)).filter(Number.isFinite);
    const total = vals.reduce((a, b) => a + b, 0);
    return {
      avg: total / (vals.length || 1),
      max: Math.max(...vals),
      min: Math.min(...vals),
    };
  }, [rows]);

  const rfConf = meta?.rf_confusion_matrix;

  return (
    <div>
      <h1>Feature 1: Demand Forecasting</h1>
      <p className="small-muted">Linear Regression vs Random Forest (date-based split)</p>

      <div className="page-card">
        <div className="input-row">
          <div className="input-box">
            <label>Forecast Horizon (days)</label>
            <input type="number" min="1" max="30" value={days} onChange={(e) => setDays(e.target.value)} />
          </div>
          <button className="btn" onClick={onRunForecast} disabled={loading}>
            {loading ? "Running..." : "Run Forecast"}
          </button>
        </div>

        {error && <div className="error">{error}</div>}
        {meta && (
          <div className="small-muted" style={{ marginTop: 8 }}>
            Chosen model: {meta.chosen_model} | Data until {meta.split_date} used for training | Data after {meta.split_date} used for testing
          </div>
        )}
      </div>

      {meta?.model_metrics && (
        <div className="kpi-grid">
          <Kpi label="LR MAE" value={meta.model_metrics.linear_regression.mae} />
          <Kpi label="LR RMSE" value={meta.model_metrics.linear_regression.rmse} />
          <Kpi label="LR R2" value={meta.model_metrics.linear_regression.r2} />
          <Kpi label="RF MAE" value={meta.model_metrics.random_forest.mae} />
          <Kpi label="RF RMSE" value={meta.model_metrics.random_forest.rmse} />
          <Kpi label="RF R2" value={meta.model_metrics.random_forest.r2} />
          <Kpi label="Rows" value={meta.rows} />
          <Kpi label="SKUs" value={meta.skus} />
        </div>
      )}

      {kpis && (
        <div className="kpi-grid">
          <Kpi label="Avg Predicted" value={kpis.avg.toFixed(2)} />
          <Kpi label="Max Predicted" value={kpis.max.toFixed(2)} />
          <Kpi label="Min Predicted" value={kpis.min.toFixed(2)} />
          <Kpi label="Horizon" value={meta?.horizon_days ?? days} />
        </div>
      )}

      {rfConf && (
        <div className="page-card">
          <h3>Random Forest Confusion Matrix</h3>
          <p className="small-muted" style={{ marginTop: 6 }}>
            Class bins from test demand quantiles: LOW &lt; {rfConf.bins?.[0]} | MEDIUM &lt; {rfConf.bins?.[1]} | HIGH otherwise
          </p>
          <div style={{ marginTop: 10 }}>
            <Plot
              data={[
                {
                  z: rfConf.matrix,
                  x: rfConf.labels,
                  y: rfConf.labels,
                  text: rfConf.matrix,
                  type: "heatmap",
                  colorscale: "Blues",
                  showscale: true,
                  texttemplate: "%{text}",
                  textfont: { size: 18, color: "#0f172a" },
                  hovertemplate: "Pred: %{x}<br>Actual: %{y}<br>Count: %{z}<extra></extra>",
                },
              ]}
              layout={{
                width: 620,
                height: 420,
                margin: { l: 70, r: 20, t: 20, b: 70 },
                xaxis: { title: "Predicted class" },
                yaxis: { title: "Actual class" },
                paper_bgcolor: "rgba(0,0,0,0)",
                plot_bgcolor: "rgba(0,0,0,0)",
              }}
              config={{ displayModeBar: false, responsive: true }}
              style={{ width: "100%" }}
            />
          </div>
        </div>
      )}

      {rows.length > 0 && (
        <div className="page-card">
          <h3>Forecast Output</h3>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>SKU</th>
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
          </div>
        </div>
      )}
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
