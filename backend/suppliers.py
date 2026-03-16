import numpy as np
import pandas as pd

def compute_supplier_scores_from_ops(ops: pd.DataFrame) -> dict:
    df = ops.copy()

    df["Units_Sold"] = pd.to_numeric(df["Units_Sold"], errors="coerce").fillna(0)
    df["Inventory_Level"] = pd.to_numeric(df["Inventory_Level"], errors="coerce").fillna(0)
    df["Supplier_Lead_Time_Days"] = pd.to_numeric(df["Supplier_Lead_Time_Days"], errors="coerce").fillna(0)

    # stockout proxy (since Stockout_Flag is all 0 in your dataset)
    df["Derived_Stockout"] = (df["Inventory_Level"] < df["Units_Sold"]).astype(int)

    # supplier baseline lead time
    sup_med = df.groupby("Supplier_ID")["Supplier_Lead_Time_Days"].median()
    df = df.join(sup_med, on="Supplier_ID", rsuffix="_median")
    df["Delay_Event"] = (df["Supplier_Lead_Time_Days"] > df["Supplier_Lead_Time_Days_median"]).astype(int)

    agg = df.groupby("Supplier_ID").agg(
        delay_pct=("Delay_Event","mean"),
        lead_std=("Supplier_Lead_Time_Days","std"),
        stockout_proxy=("Derived_Stockout","mean"),
        n=("Supplier_Lead_Time_Days","count")
    ).reset_index()

    agg["lead_std"] = agg["lead_std"].fillna(0)
    max_std = float(agg["lead_std"].max() or 1.0)

    # Components:
    # - Delay penalty: lower delay_pct better
    # - Fulfillment proxy: 1 - stockout_proxy
    # - Consistency: 1 - normalized std
    agg["fulfillment_rate"] = 1.0 - agg["stockout_proxy"]
    agg["consistency"] = 1.0 - (agg["lead_std"] / max_std)

    # Final score (0..1)
    agg["score"] = (
        0.40 * (1.0 - agg["delay_pct"]) +
        0.40 * agg["fulfillment_rate"] +
        0.20 * agg["consistency"]
    ).clip(0, 1)

    def risk_label(s):
        if s >= 0.80: return "LOW"
        if s >= 0.60: return "MEDIUM"
        return "HIGH"

    agg["risk"] = agg["score"].apply(risk_label)

    # dict for fast lookup
    out = {}
    for _, r in agg.iterrows():
        out[str(r["Supplier_ID"])] = {
            "supplier": str(r["Supplier_ID"]),
            "delay_pct": round(float(r["delay_pct"]), 3),
            "fulfillment_rate": round(float(r["fulfillment_rate"]), 3),
            "consistency": round(float(r["consistency"]), 3),
            "score": round(float(r["score"]), 3),
            "risk": r["risk"],
            "n": int(r["n"])
        }
    return out
