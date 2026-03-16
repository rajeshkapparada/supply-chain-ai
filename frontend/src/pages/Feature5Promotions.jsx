import { useEffect, useMemo, useState } from "react";
import { getPromoEvents } from "../services/api";

export default function Feature5Promotions() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    refresh();
  }, []);

  async function refresh() {
    setLoading(true);
    setError("");
    try {
      const data = await getPromoEvents(400);
      setRows(data.rows || []);
    } catch (e) {
      setError(e.message || "Unable to load promotion events");
      setRows([]);
    } finally {
      setLoading(false);
    }
  }

  const stats = useMemo(() => {
    if (!rows.length) return null;
    const promo = rows.filter((r) => r.promo === "YES").map((r) => Number(r.unitsSold) || 0);
    const non = rows.filter((r) => r.promo === "NO").map((r) => Number(r.unitsSold) || 0);

    const pAvg = promo.reduce((a, b) => a + b, 0) / (promo.length || 1);
    const nAvg = non.reduce((a, b) => a + b, 0) / (non.length || 1);
    const uplift = nAvg > 0 ? ((pAvg - nAvg) / nAvg) * 100 : 0;

    const promoStockout = rows.filter((r) => r.promo === "YES" && r.stockout === "YES").length / (rows.filter((r) => r.promo === "YES").length || 1);
    const nonStockout = rows.filter((r) => r.promo === "NO" && r.stockout === "YES").length / (rows.filter((r) => r.promo === "NO").length || 1);

    return { pAvg, nAvg, uplift, promoStockout, nonStockout };
  }, [rows]);

  return (
    <div>
      <h1>Feature 5: Promotions and Stockouts</h1>
      <p className="small-muted">Promotion uplift and stockout impact over recent events.</p>

      <div className="page-card">
        <button className="btn" onClick={refresh} disabled={loading}>{loading ? "Refreshing..." : "Refresh"}</button>
        {error && <div className="error">{error}</div>}
      </div>

      {stats && (
        <div className="kpi-grid">
          <Kpi label="Promo avg units" value={stats.pAvg.toFixed(2)} />
          <Kpi label="Non-promo avg units" value={stats.nAvg.toFixed(2)} />
          <Kpi label="Uplift %" value={stats.uplift.toFixed(2)} />
          <Kpi label="Promo stockout rate" value={stats.promoStockout.toFixed(3)} />
          <Kpi label="Non-promo stockout rate" value={stats.nonStockout.toFixed(3)} />
          <Kpi label="Events" value={rows.length} />
        </div>
      )}

      <div className="page-card">
        <h3>Recent events</h3>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Date</th>
                <th>SKU</th>
                <th>Promo</th>
                <th>Units</th>
                <th>Stockout</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 200).map((r, i) => (
                <tr key={i}>
                  <td>{r.date}</td>
                  <td>{r.sku}</td>
                  <td>{r.promo}</td>
                  <td>{r.unitsSold}</td>
                  <td>{r.stockout}</td>
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
