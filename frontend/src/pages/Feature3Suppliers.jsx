import { useEffect, useState } from "react";
import { getSupplierScores } from "../services/api";

export default function Feature3Suppliers() {
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
      const data = await getSupplierScores();
      setRows(data.suppliers || []);
    } catch (e) {
      setError(e.message || "Unable to load supplier scores");
      setRows([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h1>Feature 3: Supplier Reliability Agent</h1>

      <div className="page-card">
        <button className="btn" onClick={refresh} disabled={loading}>{loading ? "Refreshing..." : "Refresh Scores"}</button>
        {error && <div className="error">{error}</div>}

        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Supplier</th>
                <th>Score</th>
                <th>Risk</th>
                <th>Delay %</th>
                <th>Fulfillment %</th>
                <th>Consistency %</th>
                <th>Records</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((s, i) => (
                <tr key={i}>
                  <td>{s.supplier}</td>
                  <td>{Number(s.score).toFixed(3)}</td>
                  <td>{s.risk}</td>
                  <td>{(Number(s.delay_pct) * 100).toFixed(1)}</td>
                  <td>{(Number(s.fulfillment_rate) * 100).toFixed(1)}</td>
                  <td>{(Number(s.consistency) * 100).toFixed(1)}</td>
                  <td>{s.n}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
