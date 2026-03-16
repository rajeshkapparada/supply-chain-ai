import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getAnalyticsSummary } from "../services/api";

export default function DashboardHome() {
  const navigate = useNavigate();
  const [kpis, setKpis] = useState(null);
  const [promo, setPromo] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const data = await getAnalyticsSummary();
        setKpis(data.kpis || null);
        setPromo(data.promo_uplift || null);
      } catch {
        setKpis(null);
        setPromo(null);
      }
    })();
  }, []);

  return (
    <div>
      <h1>Dashboard</h1>
      <p className="small-muted">Agentic AI Inventory and Supply Chain Intelligence System</p>

      <div className="kpi-grid">
        <Kpi label="Rows" value={kpis?.rows ?? "-"} />
        <Kpi label="SKUs" value={kpis?.skus ?? "-"} />
        <Kpi label="Warehouses" value={kpis?.warehouses ?? "-"} />
        <Kpi label="Suppliers" value={kpis?.suppliers ?? "-"} />
      </div>

      <div className="page-card">
        <h3>Promotion Insight</h3>
        <p className="small-muted" style={{ marginTop: 6 }}>
          Promo avg: {promo ? promo.promo_avg.toFixed(2) : "-"} | Non-promo avg: {promo ? promo.nonpromo_avg.toFixed(2) : "-"} | Uplift: {promo ? promo.uplift_pct.toFixed(2) : "-"}%
        </p>
      </div>

      <div className="page-card">
        <h3>Features</h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 10, marginTop: 10 }}>
          <button className="btn" onClick={() => navigate("/forecast")}>Feature 1: Forecasting</button>
          <button className="btn" onClick={() => navigate("/inventory")}>Feature 2: Inventory</button>
          <button className="btn" onClick={() => navigate("/suppliers")}>Feature 3: Suppliers</button>
          <button className="btn" onClick={() => navigate("/regions")}>Feature 4: Regions</button>
          <button className="btn" onClick={() => navigate("/promotions")}>Feature 5: Promotions</button>
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
