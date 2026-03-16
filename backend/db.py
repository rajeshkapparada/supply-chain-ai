import argparse
import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).parent / "supplychain.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS daily_operations (
  Date TEXT NOT NULL,
  SKU_ID TEXT NOT NULL,
  Warehouse_ID TEXT NOT NULL,
  Supplier_ID TEXT NOT NULL,
  Region TEXT NOT NULL,
  Units_Sold REAL NOT NULL,
  Inventory_Level REAL NOT NULL,
  Supplier_Lead_Time_Days REAL NOT NULL,
  Reorder_Point REAL NOT NULL,
  Order_Quantity REAL NOT NULL,
  Unit_Cost REAL NOT NULL,
  Unit_Price REAL NOT NULL,
  Promotion_Flag INTEGER NOT NULL,
  Stockout_Flag INTEGER NOT NULL,
  Demand_Forecast REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ops_date ON daily_operations(Date);
CREATE INDEX IF NOT EXISTS idx_ops_sku_date ON daily_operations(SKU_ID, Date);
CREATE INDEX IF NOT EXISTS idx_ops_supplier ON daily_operations(Supplier_ID);
CREATE INDEX IF NOT EXISTS idx_ops_region ON daily_operations(Region);
CREATE INDEX IF NOT EXISTS idx_ops_wh ON daily_operations(Warehouse_ID);

CREATE TABLE IF NOT EXISTS forecast_runs (
  run_id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  split_date TEXT NOT NULL,
  horizon_days INTEGER NOT NULL,
  chosen_model TEXT NOT NULL,
  lr_mae REAL NOT NULL,
  lr_rmse REAL NOT NULL,
  lr_r2 REAL NOT NULL,
  rf_mae REAL NOT NULL,
  rf_rmse REAL NOT NULL,
  rf_r2 REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS forecast_predictions (
  pred_id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL,
  SKU_ID TEXT NOT NULL,
  forecast_date TEXT NOT NULL,
  predicted_units REAL NOT NULL,
  model_name TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(run_id) REFERENCES forecast_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_preds_run ON forecast_predictions(run_id);
CREATE INDEX IF NOT EXISTS idx_preds_sku_date ON forecast_predictions(SKU_ID, forecast_date);

CREATE TABLE IF NOT EXISTS mcp_decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  run_id INTEGER NOT NULL,
  day TEXT NOT NULL,
  sku TEXT NOT NULL,
  warehouse TEXT NOT NULL,
  inventory REAL NOT NULL,
  reorder_point REAL NOT NULL,
  daily_demand REAL NOT NULL,
  lead_time_days REAL NOT NULL,
  days_cover REAL NOT NULL,
  stockout_risk REAL NOT NULL,
  recommended_action TEXT NOT NULL,
  recommended_qty REAL NOT NULL,
  status TEXT NOT NULL,
  suppliers_alloc_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_mcp_run_id ON mcp_decisions(run_id);
CREATE INDEX IF NOT EXISTS idx_mcp_created_at ON mcp_decisions(created_at);
"""

REQUIRED_COLS = [
    "Date", "SKU_ID", "Warehouse_ID", "Supplier_ID", "Region", "Units_Sold",
    "Inventory_Level", "Supplier_Lead_Time_Days", "Reorder_Point", "Order_Quantity",
    "Unit_Cost", "Unit_Price", "Promotion_Flag", "Stockout_Flag", "Demand_Forecast"
]


def connect():
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    con.execute("PRAGMA busy_timeout=5000;")
    con.execute("PRAGMA foreign_keys=ON;")
    return con


def _migrate_mcp_decisions(con: sqlite3.Connection) -> None:
    expected = {
        "day": "TEXT NOT NULL DEFAULT ''",
        "suppliers_alloc_json": "TEXT",
    }
    cols = {
        row[1]
        for row in con.execute("PRAGMA table_info(mcp_decisions)").fetchall()
    }
    for col_name, col_type in expected.items():
        if col_name not in cols:
            con.execute(
                f"ALTER TABLE mcp_decisions ADD COLUMN {col_name} {col_type}"
            )


def init_db():
    with connect() as con:
        con.executescript(SCHEMA_SQL)
        _migrate_mcp_decisions(con)
    print(f"[OK] DB initialized at: {DB_PATH}")


def load_csv(csv_path: str):
    p = Path(csv_path)
    if not p.exists():
        raise FileNotFoundError(f"CSV not found: {p}")

    df = pd.read_csv(p)

    missing = sorted(list(set(REQUIRED_COLS) - set(df.columns)))
    if missing:
        raise ValueError(f"CSV missing columns: {missing}")

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.date.astype(str)
    df = df.dropna(subset=["Date", "SKU_ID", "Units_Sold"])

    num_cols = [
        "Units_Sold", "Inventory_Level", "Supplier_Lead_Time_Days", "Reorder_Point",
        "Order_Quantity", "Unit_Cost", "Unit_Price", "Promotion_Flag",
        "Stockout_Flag", "Demand_Forecast"
    ]
    for c in num_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    with connect() as con:
        con.execute("DELETE FROM daily_operations;")
        df.to_sql("daily_operations", con, if_exists="append", index=False)

    print(f"[OK] Loaded {len(df):,} rows into daily_operations")


def show_tables():
    with connect() as con:
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    print("Tables:")
    for r in rows:
        print(" -", r[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", action="store_true", help="Initialize schema")
    ap.add_argument("--load-csv", type=str, default=None, help="Load CSV into daily_operations")
    ap.add_argument("--show-tables", action="store_true", help="Print all table names")
    args = ap.parse_args()

    if args.init:
        init_db()

    if args.load_csv:
        init_db()
        load_csv(args.load_csv)

    if args.show_tables:
        show_tables()


if __name__ == "__main__":
    main()
