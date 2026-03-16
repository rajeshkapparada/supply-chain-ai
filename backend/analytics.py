import pandas as pd
import numpy as np

def add_derived_fields(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
    out = out.dropna(subset=["Date"])
    out["Units_Sold"] = pd.to_numeric(out["Units_Sold"], errors="coerce").fillna(0)
    out["Inventory_Level"] = pd.to_numeric(out["Inventory_Level"], errors="coerce").fillna(0)
    out["Promotion_Flag"] = pd.to_numeric(out["Promotion_Flag"], errors="coerce").fillna(0).astype(int)

    # Stockout proxy because Stockout_Flag is all 0 in dataset
    out["Derived_Stockout"] = (out["Inventory_Level"] < out["Units_Sold"]).astype(int)

    out["Revenue"] = pd.to_numeric(out["Unit_Price"], errors="coerce").fillna(0) * out["Units_Sold"]
    out["COGS"] = pd.to_numeric(out["Unit_Cost"], errors="coerce").fillna(0) * out["Units_Sold"]
    out["Margin"] = out["Revenue"] - out["COGS"]
    return out

def kpis(df: pd.DataFrame) -> dict:
    return {
        "rows": int(len(df)),
        "skus": int(df["SKU_ID"].nunique()),
        "warehouses": int(df["Warehouse_ID"].nunique()),
        "suppliers": int(df["Supplier_ID"].nunique()),
        "regions": int(df["Region"].nunique()),
        "date_min": str(df["Date"].min().date()),
        "date_max": str(df["Date"].max().date()),
        "total_units": float(df["Units_Sold"].sum()),
        "promo_rate": float(df["Promotion_Flag"].mean()),
        "derived_stockout_rate": float(df["Derived_Stockout"].mean())
    }

def demand_by_region(df: pd.DataFrame) -> pd.DataFrame:
    return df.groupby("Region", as_index=False)["Units_Sold"].sum().sort_values("Units_Sold", ascending=False)

def daily_demand(df: pd.DataFrame) -> pd.DataFrame:
    x = df.groupby("Date", as_index=False)["Units_Sold"].sum().sort_values("Date")
    return x

def promo_uplift(df: pd.DataFrame) -> dict:
    promo = df[df["Promotion_Flag"] == 1]["Units_Sold"]
    non = df[df["Promotion_Flag"] == 0]["Units_Sold"]
    promo_avg = float(promo.mean() if len(promo) else 0)
    non_avg = float(non.mean() if len(non) else 0)
    uplift = ((promo_avg - non_avg) / non_avg * 100.0) if non_avg > 0 else 0.0
    return {"promo_avg": promo_avg, "nonpromo_avg": non_avg, "uplift_pct": uplift}

def top_skus(df: pd.DataFrame, n=10) -> pd.DataFrame:
    return df.groupby("SKU_ID", as_index=False)["Units_Sold"].sum().sort_values("Units_Sold", ascending=False).head(n)
