import { useEffect, useState } from "react";
import { getDemandByRegion } from "../services/api";

export default function Feature4Regions() {
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
      const data = await getDemandByRegion();
      setRows(data.rows || []);
    } catch (e) {
      setError(e.message || "Unable to load region demand");
      setRows([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h1>Feature 4: Regional Demand Insights</h1>
      <p className="small-muted">Aggregated demand by region for planning replenishment and staffing.</p>

      <div className="page-card">
        <button className="btn" onClick={refresh} disabled={loading}>{loading ? "Refreshing..." : "Refresh"}</button>
        {error && <div className="error">{error}</div>}

        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Region</th>
                <th>Total Units Sold</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>
                  <td>{r.Region}</td>
                  <td>{Number(r.Units_Sold).toFixed(0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
