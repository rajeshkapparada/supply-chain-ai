from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta

import pandas as pd


@dataclass
class ReorderDecision:
    day: str
    sku: str
    warehouse: str
    inventory: float
    reorder_point: float
    daily_demand: float
    lead_time_days: float
    days_cover: float
    stockout_risk: float
    recommended_action: str
    recommended_qty: float
    status: str
    suppliers_alloc: list[dict]


def _soft_alloc(scores: list[tuple[str, float]], qty: float) -> list[dict]:
    scores = [(sid, max(0.0001, float(s))) for sid, s in scores]
    total = sum(s for _, s in scores)

    alloc = []
    remaining = float(qty)

    for i, (sid, s) in enumerate(scores):
        if i == len(scores) - 1:
            q = remaining
        else:
            q = float(qty) * (s / total)
            remaining -= q

        alloc.append(
            {
                "supplier": sid,
                "allocated_qty": round(float(q), 2),
                "weight": round(float(s / total), 3),
            }
        )

    return alloc


def _ensure_mcp_table(con: sqlite3.Connection) -> None:
    cur = con.cursor()
    cur.execute(
        """
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
        )
        """
    )

    existing_cols = {
        row[1] for row in cur.execute("PRAGMA table_info(mcp_decisions)").fetchall()
    }
    required_cols = {
        "day": "TEXT NOT NULL DEFAULT ''",
        "suppliers_alloc_json": "TEXT",
    }
    for col_name, col_type in required_cols.items():
        if col_name not in existing_cols:
            cur.execute(f"ALTER TABLE mcp_decisions ADD COLUMN {col_name} {col_type}")

    cur.execute("CREATE INDEX IF NOT EXISTS idx_mcp_run_id ON mcp_decisions(run_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_mcp_created_at ON mcp_decisions(created_at)")
    con.commit()


def save_mcp_decisions(con: sqlite3.Connection, run_id: int, items: list[dict]) -> None:
    _ensure_mcp_table(con)
    created_at = datetime.utcnow().isoformat(timespec="seconds")
    cur = con.cursor()

    rows = []
    for r in items:
        rows.append(
            (
                created_at,
                int(run_id),
                str(r.get("day", "")),
                str(r.get("sku", "")),
                str(r.get("warehouse", "")),
                float(r.get("inventory", 0)),
                float(r.get("reorderPoint", 0)),
                float(r.get("dailyDemand", 0)),
                float(r.get("leadTimeDays", 0)),
                float(r.get("daysCover", 0)),
                float(r.get("stockoutRisk", 0)),
                str(r.get("recommendedAction", "")),
                float(r.get("recommendedQty", 0)),
                str(r.get("status", "")),
                json.dumps(r.get("suppliersAlloc", [])),
            )
        )

    cur.executemany(
        """
        INSERT INTO mcp_decisions (
            created_at,
            run_id,
            day,
            sku,
            warehouse,
            inventory,
            reorder_point,
            daily_demand,
            lead_time_days,
            days_cover,
            stockout_risk,
            recommended_action,
            recommended_qty,
            status,
            suppliers_alloc_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    con.commit()


def run_mcp_simulation(con: sqlite3.Connection, run_id: int, horizon_days: int = 14) -> dict:
    ops = pd.read_sql_query("SELECT * FROM daily_operations", con)
    preds = pd.read_sql_query(
        """
        SELECT SKU_ID, forecast_date, predicted_units
        FROM forecast_predictions
        WHERE run_id = ?
        """,
        con,
        params=(run_id,),
    )

    if preds.empty:
        raise ValueError("No predictions found for this run_id")

    ops["Date"] = pd.to_datetime(ops["Date"], errors="coerce")
    preds["forecast_date"] = pd.to_datetime(preds["forecast_date"], errors="coerce")

    ops = ops.dropna(subset=["Date"])
    preds = preds.dropna(subset=["forecast_date"])

    if ops.empty:
        raise ValueError("daily_operations table is empty or Date parsing failed")

    last_day = ops["Date"].max()
    start_day = last_day + timedelta(days=1)

    snap = (
        ops.sort_values(["SKU_ID", "Warehouse_ID", "Date"])
        .groupby(["SKU_ID", "Warehouse_ID"])
        .tail(1)
        .copy()
    )

    snap["Inventory_Level"] = pd.to_numeric(snap["Inventory_Level"], errors="coerce").fillna(0)
    snap["Reorder_Point"] = pd.to_numeric(snap["Reorder_Point"], errors="coerce").fillna(0)

    lead_time_col = None
    for c in ["Supplier_Lead_Time_Days", "Lead_Time_Days", "Lead_Time"]:
        if c in snap.columns:
            lead_time_col = c
            break

    if lead_time_col:
        snap["Lead_Time_Days"] = pd.to_numeric(snap[lead_time_col], errors="coerce").fillna(7)
    else:
        snap["Lead_Time_Days"] = 7.0

    from suppliers import compute_supplier_scores_from_ops

    supplier_scores = compute_supplier_scores_from_ops(ops)

    if "Supplier_ID" in ops.columns:
        sku_sup = ops.groupby("SKU_ID")["Supplier_ID"].unique().to_dict()
    else:
        sku_sup = {}

    demand_map = (
        preds.groupby(["SKU_ID", "forecast_date"])["predicted_units"].sum().reset_index()
    )

    pipeline = []
    decisions: list[ReorderDecision] = []

    for step in range(horizon_days):
        day = start_day + timedelta(days=step)

        arriving = [o for o in pipeline if o["arrival_date"] == day.date().isoformat()]
        if arriving:
            for o in arriving:
                mask = (snap["SKU_ID"] == o["sku"]) & (snap["Warehouse_ID"] == o["warehouse"])
                if mask.any():
                    snap.loc[mask, "Inventory_Level"] += float(o["qty"])

        pipeline = [o for o in pipeline if o["arrival_date"] != day.date().isoformat()]

        for _, row in snap.iterrows():
            sku = row["SKU_ID"]
            warehouse = row["Warehouse_ID"]

            inventory = float(row["Inventory_Level"])
            reorder_point = float(row["Reorder_Point"])
            lead_time_days = float(row["Lead_Time_Days"])
            lt = int(max(1, round(lead_time_days)))

            dm = demand_map[(demand_map["SKU_ID"] == sku) & (demand_map["forecast_date"] == day)]
            daily_demand = float(dm["predicted_units"].iloc[0]) if len(dm) else 0.0

            projected_after = inventory - daily_demand
            days_cover = inventory / max(daily_demand, 0.0001)
            stockout_risk = max(0.0, min(1.0, (lt - days_cover) / max(lt, 1)))

            if inventory <= 0:
                status = "OUT"
            elif projected_after <= reorder_point:
                status = "LOW"
            else:
                status = "OK"

            recommended_action = "NO_ACTION"
            recommended_qty = 0.0
            suppliers_alloc = []

            if projected_after <= reorder_point:
                recommended_action = "REORDER"
                target_cover_days = lt + 7
                target_stock = (daily_demand * target_cover_days) + reorder_point
                recommended_qty = max(0.0, target_stock - projected_after)

                suppliers = list(sku_sup.get(sku, []))
                scored = []
                for sid in suppliers:
                    srow = supplier_scores.get(sid, None)
                    scored.append((sid, float(srow["score"]) if srow else 0.5))

                if not scored:
                    scored = [("UNKNOWN_SUP", 0.5)]

                suppliers_alloc = _soft_alloc(scored, recommended_qty)

                arrival = (day + timedelta(days=lt)).date().isoformat()
                pipeline.append(
                    {
                        "arrival_date": arrival,
                        "sku": sku,
                        "warehouse": warehouse,
                        "qty": float(recommended_qty),
                    }
                )

            decisions.append(
                ReorderDecision(
                    day=day.date().isoformat(),
                    sku=sku,
                    warehouse=warehouse,
                    inventory=round(inventory, 2),
                    reorder_point=round(reorder_point, 2),
                    daily_demand=round(daily_demand, 2),
                    lead_time_days=round(lead_time_days, 2),
                    days_cover=round(days_cover, 2),
                    stockout_risk=round(stockout_risk, 3),
                    recommended_action=recommended_action,
                    recommended_qty=round(recommended_qty, 2),
                    status=status,
                    suppliers_alloc=suppliers_alloc,
                )
            )

            mask = (snap["SKU_ID"] == sku) & (snap["Warehouse_ID"] == warehouse)
            snap.loc[mask, "Inventory_Level"] = projected_after

    items = []
    for d in decisions:
        items.append(
            {
                "day": d.day,
                "sku": d.sku,
                "warehouse": d.warehouse,
                "inventory": d.inventory,
                "reorderPoint": d.reorder_point,
                "dailyDemand": d.daily_demand,
                "leadTimeDays": d.lead_time_days,
                "daysCover": d.days_cover,
                "stockoutRisk": d.stockout_risk,
                "recommendedAction": d.recommended_action,
                "recommendedQty": d.recommended_qty,
                "status": d.status,
                "suppliersAlloc": d.suppliers_alloc,
            }
        )

    reorder_count = sum(1 for x in items if x["recommendedAction"] == "REORDER")

    save_mcp_decisions(con, run_id, items)

    return {
        "run_id": run_id,
        "horizon_days": horizon_days,
        "reorder_events": reorder_count,
        "rows": len(items),
        "items": items,
    }
