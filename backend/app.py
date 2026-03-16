import sqlite3
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS

from analytics import (
    add_derived_fields,
    daily_demand,
    demand_by_region,
    kpis,
    promo_uplift,
    top_skus,
)
from forecasting import run_forecast_from_db
from inventory_mcp import run_mcp_simulation
from suppliers import compute_supplier_scores_from_ops

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "supplychain.db"

app = Flask(__name__)
CORS(
    app,
    resources={r"/*": {"origins": ["http://localhost:5173", "http://127.0.0.1:5173"]}},
    supports_credentials=False,
)


def connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"DB not found at {DB_PATH}. Run: python db.py --init --load-csv data/daily_operations.csv"
        )

    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    con.execute("PRAGMA busy_timeout=5000;")
    con.execute("PRAGMA foreign_keys=ON;")
    return con


@app.errorhandler(FileNotFoundError)
def file_not_found(err):
    return jsonify({"error": str(err)}), 404


@app.errorhandler(ValueError)
def value_error(err):
    return jsonify({"error": str(err)}), 400


@app.errorhandler(Exception)
def unhandled(err):
    return jsonify({"error": f"Server error: {err}"}), 500


@app.get("/")
def home():
    return jsonify(
        {
            "message": "SupplyChain-AI API running",
            "db": str(DB_PATH),
            "try": [
                "/health",
                "/forecast/run?horizon=7",
                "/inventory/mcp/run",
                "/inventory/mcp/history?limit=50",
                "/analytics/summary",
                "/analytics/daily_demand",
                "/analytics/demand_by_region",
                "/analytics/top_skus?n=10",
                "/analytics/promo_events?limit=200",
                "/analytics/inventory_snapshot?limit=50",
                "/suppliers/score",
            ],
        }
    )


@app.get("/health")
def health():
    with connect() as con:
        rows = con.execute("SELECT COUNT(*) AS n FROM daily_operations").fetchone()
    return jsonify({"status": "ok", "db": str(DB_PATH), "daily_operations_rows": int(rows["n"])})


@app.post("/forecast/run")
def forecast_run():
    horizon = int(request.args.get("horizon", "7"))
    horizon = max(1, min(30, horizon))

    with connect() as con:
        out = run_forecast_from_db(con, horizon_days=horizon)

    # Requested by user: show model metrics in terminal too.
    lr = out["model_metrics"]["linear_regression"]
    rf = out["model_metrics"]["random_forest"]
    print(
        f"[Forecast run {out['run_id']}] LR -> MAE={lr['mae']}, RMSE={lr['rmse']}, R2={lr['r2']} | "
        f"RF -> MAE={rf['mae']}, RMSE={rf['rmse']}, R2={rf['r2']} | chosen={out['chosen_model']}"
    )

    return jsonify(
        {
            "meta": {
                "run_id": out["run_id"],
                "chosen_model": out["chosen_model"],
                "split_date": out["split_date"],
                "horizon_days": out["horizon_days"],
                "skus": out["skus"],
                "rows": out["rows"],
                "metrics": out["metrics"],
                "model_metrics": out["model_metrics"],
                "rf_confusion_matrix": out["rf_confusion_matrix"],
            },
            "rows": out["predictions"],
        }
    )


@app.post("/inventory/mcp/run")
def inventory_mcp_run():
    payload = request.get_json(force=True) or {}
    run_id = int(payload.get("run_id", 0))
    horizon_days = int(payload.get("horizon_days", 14))
    horizon_days = max(1, min(30, horizon_days))

    if run_id <= 0:
        raise ValueError("Provide run_id from /forecast/run result")

    with connect() as con:
        out = run_mcp_simulation(con, run_id=run_id, horizon_days=horizon_days)

    return jsonify(out)


@app.get("/inventory/mcp/history")
def inventory_mcp_history():
    limit = int(request.args.get("limit", "200"))
    limit = max(10, min(2000, limit))

    with connect() as con:
        cols = pd.read_sql_query("PRAGMA table_info(mcp_decisions)", con)
        if cols.empty:
            return jsonify(
                {
                    "rows": [],
                    "meta": {
                        "count": 0,
                        "message": "mcp_decisions table not found yet. Run MCP once.",
                    },
                }
            )

        col_names = set(cols["name"].tolist())
        select_cols = [
            "created_at",
            "run_id",
            "day" if "day" in col_names else "'' AS day",
            "sku",
            "warehouse",
            "inventory",
            "reorder_point",
            "daily_demand",
            "lead_time_days",
            "days_cover",
            "stockout_risk",
            "recommended_action",
            "recommended_qty",
            "status",
            "suppliers_alloc_json" if "suppliers_alloc_json" in col_names else "NULL AS suppliers_alloc_json",
        ]
        select_sql = ",\n                ".join(select_cols)

        df = pd.read_sql_query(
            f"""
            SELECT
                {select_sql}
            FROM mcp_decisions
            ORDER BY id DESC
            LIMIT ?
            """,
            con,
            params=(limit,),
        )

    return jsonify({"rows": df.to_dict(orient="records"), "meta": {"count": len(df)}})


@app.get("/suppliers/score")
def suppliers_score():
    with connect() as con:
        ops = pd.read_sql_query("SELECT * FROM daily_operations", con)

    ops = add_derived_fields(ops)
    scores = compute_supplier_scores_from_ops(ops)
    rows = sorted(scores.values(), key=lambda x: x["score"], reverse=True)

    return jsonify({"suppliers": rows, "meta": {"count": len(rows)}})


@app.get("/analytics/summary")
def analytics_summary():
    with connect() as con:
        ops = pd.read_sql_query("SELECT * FROM daily_operations", con)

    ops = add_derived_fields(ops)
    return jsonify({"kpis": kpis(ops), "promo_uplift": promo_uplift(ops)})


@app.get("/analytics/top_skus")
def analytics_top_skus():
    n = int(request.args.get("n", "10"))
    n = max(1, min(50, n))

    with connect() as con:
        ops = pd.read_sql_query("SELECT * FROM daily_operations", con)

    ops = add_derived_fields(ops)
    t = top_skus(ops, n=n)
    return jsonify({"rows": t.to_dict(orient="records")})


@app.get("/analytics/demand_by_region")
def analytics_region():
    with connect() as con:
        ops = pd.read_sql_query("SELECT * FROM daily_operations", con)

    ops = add_derived_fields(ops)
    r = demand_by_region(ops)
    return jsonify({"rows": r.to_dict(orient="records")})


@app.get("/analytics/daily_demand")
def analytics_daily():
    with connect() as con:
        ops = pd.read_sql_query("SELECT * FROM daily_operations", con)

    ops = add_derived_fields(ops)
    d = daily_demand(ops)
    d["Date"] = d["Date"].dt.date.astype(str)
    return jsonify({"rows": d.to_dict(orient="records")})


@app.get("/analytics/promo_events")
def analytics_promo_events():
    limit = int(request.args.get("limit", "200"))
    limit = max(10, min(5000, limit))

    with connect() as con:
        ops = pd.read_sql_query(
            """
            SELECT Date, SKU_ID, Promotion_Flag, Units_Sold, Inventory_Level
            FROM daily_operations
            ORDER BY Date DESC
            LIMIT ?
            """,
            con,
            params=(limit,),
        )

    ops["Date"] = pd.to_datetime(ops["Date"], errors="coerce").dt.date.astype(str)
    ops["Promotion_Flag"] = pd.to_numeric(ops["Promotion_Flag"], errors="coerce").fillna(0).astype(int)
    ops["Units_Sold"] = pd.to_numeric(ops["Units_Sold"], errors="coerce").fillna(0)
    ops["Inventory_Level"] = pd.to_numeric(ops["Inventory_Level"], errors="coerce").fillna(0)
    ops["Derived_Stockout"] = (ops["Inventory_Level"] < ops["Units_Sold"]).astype(int)

    rows = []
    for _, r in ops.iterrows():
        rows.append(
            {
                "date": r["Date"],
                "sku": r["SKU_ID"],
                "promo": "YES" if int(r["Promotion_Flag"]) == 1 else "NO",
                "unitsSold": float(r["Units_Sold"]),
                "stockout": "YES" if int(r["Derived_Stockout"]) == 1 else "NO",
            }
        )

    return jsonify({"rows": rows, "meta": {"count": len(rows)}})


@app.get("/analytics/inventory_snapshot")
def analytics_inventory_snapshot():
    limit = int(request.args.get("limit", "50"))
    limit = max(10, min(500, limit))

    with connect() as con:
        cols = pd.read_sql_query("PRAGMA table_info(daily_operations);", con)
        col_names = set(cols["name"].tolist())

        lead_candidates = [
            "Lead_Time_Days",
            "Lead_Time",
            "LeadTimeDays",
            "LeadTime",
            "Supplier_Lead_Time",
            "Supplier_Lead_Time_Days",
            "Avg_Lead_Time_Days",
        ]
        lead_col = next((c for c in lead_candidates if c in col_names), None)
        lead_select = f'"{lead_col}" AS Lead_Time' if lead_col else "NULL AS Lead_Time"

        snap = pd.read_sql_query(
            f"""
            WITH ranked AS (
              SELECT
                Date,
                SKU_ID,
                Warehouse_ID,
                Inventory_Level,
                Reorder_Point,
                {lead_select},
                ROW_NUMBER() OVER(
                  PARTITION BY SKU_ID, Warehouse_ID
                  ORDER BY Date DESC
                ) AS rn
              FROM daily_operations
            )
            SELECT
              Date,
              SKU_ID,
              Warehouse_ID,
              Inventory_Level,
              Reorder_Point,
              Lead_Time
            FROM ranked
            WHERE rn = 1
            LIMIT ?
            """,
            con,
            params=(limit,),
        )

        demand = pd.read_sql_query(
            """
            SELECT
                SKU_ID,
                Warehouse_ID,
                AVG(Units_Sold) AS avg_daily_demand
            FROM daily_operations
            WHERE Date >= date((SELECT MAX(Date) FROM daily_operations), '-14 day')
            GROUP BY SKU_ID, Warehouse_ID
            """,
            con,
        )

    if snap.empty:
        return jsonify(
            {
                "rows": [],
                "meta": {
                    "count": 0,
                    "lead_time_column_used": lead_col or "DEFAULT_7_DAYS",
                },
            }
        )

    df = snap.merge(demand, on=["SKU_ID", "Warehouse_ID"], how="left")
    df["avg_daily_demand"] = df["avg_daily_demand"].fillna(0)
    df["Lead_Time"] = pd.to_numeric(df["Lead_Time"], errors="coerce").fillna(7)

    rows = []
    for _, r in df.iterrows():
        rows.append(
            {
                "sku": r["SKU_ID"],
                "warehouse": r["Warehouse_ID"],
                "inventory": float(r["Inventory_Level"]),
                "reorderPoint": float(r["Reorder_Point"]),
                "dailyDemand": float(r["avg_daily_demand"]) if float(r["avg_daily_demand"]) > 0 else 10.0,
                "leadTimeDays": float(r["Lead_Time"]) if float(r["Lead_Time"]) > 0 else 7.0,
            }
        )

    return jsonify(
        {
            "rows": rows,
            "meta": {
                "count": len(rows),
                "lead_time_column_used": lead_col or "DEFAULT_7_DAYS",
            },
        }
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)
