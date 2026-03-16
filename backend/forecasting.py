import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import confusion_matrix, mean_absolute_error, mean_squared_error, r2_score


@dataclass
class ModelMetrics:
    mae: float
    rmse: float
    r2: float


def _metrics(y_true, y_pred) -> ModelMetrics:
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    try:
        r2 = float(r2_score(y_true, y_pred))
    except Exception:
        r2 = 0.0
    if np.isnan(r2):
        r2 = 0.0
    return ModelMetrics(mae, rmse, r2)


def _first_existing(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _ensure_forecast_tables(con: sqlite3.Connection) -> None:
    cur = con.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS forecast_runs(
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
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS forecast_predictions(
            pred_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            SKU_ID TEXT NOT NULL,
            forecast_date TEXT NOT NULL,
            predicted_units REAL NOT NULL,
            model_name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES forecast_runs(run_id)
        )
        """
    )
    con.commit()


def _prepare_ops(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, str]]:
    df = df.copy()
    colmap = {}

    date_col = _first_existing(df, ["Date", "date", "DATE"])
    sku_col = _first_existing(df, ["SKU_ID", "SKU", "sku_id", "sku"])
    units_col = _first_existing(df, ["Units_Sold", "units_sold", "Sales", "sales", "Demand", "demand"])

    if not date_col or not sku_col or not units_col:
        raise ValueError(
            "DB missing required columns. Need Date, SKU_ID, Units_Sold (or variants)."
        )

    promo_col = _first_existing(df, ["Promotion_Flag", "promo", "Promo_Flag", "Promotion"])
    inv_col = _first_existing(df, ["Inventory_Level", "inventory", "Inventory", "Stock_Level"])
    rp_col = _first_existing(df, ["Reorder_Point", "reorder_point", "ROP"])
    lt_col = _first_existing(df, ["Supplier_Lead_Time_Days", "Lead_Time_Days", "Lead_Time", "LeadTimeDays"])
    base_fc_col = _first_existing(df, ["Demand_Forecast", "Base_Forecast", "Forecast"])

    colmap["Date"] = date_col
    colmap["SKU_ID"] = sku_col
    colmap["Units_Sold"] = units_col
    colmap["Promotion_Flag"] = promo_col or ""
    colmap["Inventory_Level"] = inv_col or ""
    colmap["Reorder_Point"] = rp_col or ""
    colmap["Supplier_Lead_Time_Days"] = lt_col or ""
    colmap["Demand_Forecast"] = base_fc_col or ""

    df["Date"] = pd.to_datetime(df[date_col], errors="coerce")
    df["SKU_ID"] = df[sku_col].astype(str)
    df["Units_Sold"] = pd.to_numeric(df[units_col], errors="coerce").fillna(0.0)

    df["Promotion_Flag"] = (
        pd.to_numeric(df[promo_col], errors="coerce").fillna(0).astype(int)
        if promo_col else 0
    )
    df["Inventory_Level"] = (
        pd.to_numeric(df[inv_col], errors="coerce").fillna(0.0)
        if inv_col else 0.0
    )
    df["Reorder_Point"] = (
        pd.to_numeric(df[rp_col], errors="coerce").fillna(0.0)
        if rp_col else 0.0
    )
    df["Supplier_Lead_Time_Days"] = (
        pd.to_numeric(df[lt_col], errors="coerce").fillna(7.0)
        if lt_col else 7.0
    )
    df["Demand_Forecast"] = (
        pd.to_numeric(df[base_fc_col], errors="coerce").fillna(0.0)
        if base_fc_col else 0.0
    )

    df = df.dropna(subset=["Date"]).sort_values(["SKU_ID", "Date"])
    return df, colmap


def build_features(df_ops: pd.DataFrame, lags: List[int], roll_window: int) -> pd.DataFrame:
    df = df_ops.copy()
    df["dow"] = df["Date"].dt.dayofweek
    df["month"] = df["Date"].dt.month

    for lag in lags:
        df[f"lag_{lag}"] = df.groupby("SKU_ID")["Units_Sold"].shift(lag)

    df[f"roll{roll_window}_mean"] = (
        df.groupby("SKU_ID")["Units_Sold"]
        .shift(1)
        .rolling(roll_window)
        .mean()
        .reset_index(level=0, drop=True)
    )

    needed = [f"lag_{l}" for l in lags] + [f"roll{roll_window}_mean"]
    df = df.dropna(subset=needed)
    return df


def date_split(df_feat: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, str]:
    all_dates = df_feat["Date"].sort_values().unique()
    if len(all_dates) < 2:
        split_date = pd.to_datetime(df_feat["Date"].max())
        return df_feat.copy(), df_feat.iloc[0:0].copy(), split_date.date().isoformat()

    split_idx = int(len(all_dates) * 0.8)
    split_idx = max(1, min(split_idx, len(all_dates) - 1))
    split_date = pd.to_datetime(all_dates[split_idx])

    train = df_feat[df_feat["Date"] <= split_date].copy()
    test = df_feat[df_feat["Date"] > split_date].copy()
    return train, test, split_date.date().isoformat()


def _build_rf_confusion(y_true, y_pred) -> dict:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)

    if len(y_true) < 3:
        return {
            "labels": ["LOW", "MEDIUM", "HIGH"],
            "matrix": [[0, 0, 0], [0, 0, 0], [0, 0, 0]],
            "bins": [0.0, 0.0],
        }

    q1, q2 = np.quantile(y_true, [0.33, 0.66])
    if q1 == q2:
        mean = float(np.mean(y_true))
        q1 = mean * 0.75
        q2 = mean * 1.25

    true_cls = np.digitize(y_true, bins=[q1, q2], right=False)
    pred_cls = np.digitize(y_pred, bins=[q1, q2], right=False)

    cm = confusion_matrix(true_cls, pred_cls, labels=[0, 1, 2])
    return {
        "labels": ["LOW", "MEDIUM", "HIGH"],
        "matrix": cm.astype(int).tolist(),
        "bins": [round(float(q1), 3), round(float(q2), 3)],
    }


def train_and_select(
    train: pd.DataFrame, test: pd.DataFrame, feature_cols: List[str]
) -> Tuple[str, object, ModelMetrics, ModelMetrics, dict]:
    X_train, y_train = train[feature_cols], train["Units_Sold"]

    if len(test) == 0:
        X_test, y_test = X_train, y_train
    else:
        X_test, y_test = test[feature_cols], test["Units_Sold"]

    lr = LinearRegression()
    lr.fit(X_train, y_train)
    lr_pred = lr.predict(X_test)
    lr_m = _metrics(y_test, lr_pred)

    rf = RandomForestRegressor(
        n_estimators=250,
        random_state=42,
        n_jobs=-1,
        min_samples_leaf=2,
    )
    rf.fit(X_train, y_train)
    rf_pred = rf.predict(X_test)
    rf_m = _metrics(y_test, rf_pred)

    rf_conf = _build_rf_confusion(y_test, rf_pred)

    chosen_name, chosen_model = (
        ("RandomForest", rf) if rf_m.mae <= lr_m.mae else ("LinearRegression", lr)
    )
    return chosen_name, chosen_model, lr_m, rf_m, rf_conf


def iterative_forecast(
    model,
    df_ops: pd.DataFrame,
    horizon_days: int,
    lags: List[int],
    roll_window: int,
) -> pd.DataFrame:
    df_ops = df_ops.copy().sort_values(["SKU_ID", "Date"])
    last_date = df_ops["Date"].max().date()

    latest = df_ops.groupby("SKU_ID").tail(1).set_index("SKU_ID")
    out = []
    max_lag = max(lags)

    for sku, g in df_ops.groupby("SKU_ID"):
        g = g.sort_values("Date")
        history = list(g["Units_Sold"].astype(float).values)

        if len(history) < max_lag + 1:
            avg = float(np.mean(history)) if len(history) else 0.0
            for step in range(1, horizon_days + 1):
                out.append(
                    {
                        "SKU_ID": sku,
                        "forecast_date": (last_date + timedelta(days=step)).isoformat(),
                        "predicted_units": round(avg, 2),
                    }
                )
            continue

        inv = float(latest.loc[sku]["Inventory_Level"]) if sku in latest.index else 0.0
        rp = float(latest.loc[sku]["Reorder_Point"]) if sku in latest.index else 0.0
        lt = float(latest.loc[sku]["Supplier_Lead_Time_Days"]) if sku in latest.index else 7.0
        base_fc = float(latest.loc[sku]["Demand_Forecast"]) if sku in latest.index else 0.0

        for step in range(1, horizon_days + 1):
            future_date = last_date + timedelta(days=step)
            dow = pd.Timestamp(future_date).dayofweek
            month = pd.Timestamp(future_date).month

            feats = {}
            for lag in lags:
                feats[f"lag_{lag}"] = history[-lag]

            feats[f"roll{roll_window}_mean"] = float(np.mean(history[-roll_window:]))

            Xf = [feats[f"lag_{lag}"] for lag in lags] + [
                feats[f"roll{roll_window}_mean"],
                dow,
                month,
                0,
                inv,
                rp,
                lt,
                base_fc,
            ]

            pred = float(model.predict(np.array([Xf]))[0])
            pred = max(0.0, pred)

            out.append(
                {
                    "SKU_ID": sku,
                    "forecast_date": future_date.isoformat(),
                    "predicted_units": round(pred, 2),
                }
            )
            history.append(pred)

    return pd.DataFrame(out)


def save_run_and_predictions(
    con: sqlite3.Connection,
    split_date: str,
    horizon_days: int,
    chosen_model: str,
    lr_m: ModelMetrics,
    rf_m: ModelMetrics,
    preds: pd.DataFrame,
) -> int:
    _ensure_forecast_tables(con)
    created_at = datetime.utcnow().isoformat(timespec="seconds")
    cur = con.cursor()
    cur.execute(
        """
        INSERT INTO forecast_runs(created_at, split_date, horizon_days, chosen_model,
                                  lr_mae, lr_rmse, lr_r2, rf_mae, rf_rmse, rf_r2)
        VALUES(?,?,?,?,?,?,?,?,?,?)
        """,
        (
            created_at,
            split_date,
            horizon_days,
            chosen_model,
            lr_m.mae,
            lr_m.rmse,
            lr_m.r2,
            rf_m.mae,
            rf_m.rmse,
            rf_m.r2,
        ),
    )
    run_id = cur.lastrowid

    if len(preds) > 0:
        rows = [
            (
                run_id,
                r["SKU_ID"],
                r["forecast_date"],
                float(r["predicted_units"]),
                chosen_model,
                created_at,
            )
            for _, r in preds.iterrows()
        ]
        cur.executemany(
            """
            INSERT INTO forecast_predictions(run_id, SKU_ID, forecast_date, predicted_units, model_name, created_at)
            VALUES(?,?,?,?,?,?)
            """,
            rows,
        )
    con.commit()
    return int(run_id)


def run_forecast_from_db(con: sqlite3.Connection, horizon_days: int) -> dict:
    df_raw = pd.read_sql_query("SELECT * FROM daily_operations", con)
    df_ops, _colmap = _prepare_ops(df_raw)

    attempts = [([1, 7, 14], 7), ([1, 3, 7], 3), ([1, 2], 2)]
    df_feat = None
    used_lags, used_roll = None, None

    for lags, rollw in attempts:
        tmp = build_features(df_ops, lags=lags, roll_window=rollw)
        if len(tmp) >= 30:
            df_feat = tmp
            used_lags, used_roll = lags, rollw
            break

    if df_feat is None or used_lags is None or used_roll is None:
        last_date = df_ops["Date"].max().date()
        preds = []
        for sku, g in df_ops.groupby("SKU_ID"):
            avg = float(g["Units_Sold"].mean()) if len(g) else 0.0
            for step in range(1, horizon_days + 1):
                preds.append(
                    {
                        "SKU_ID": sku,
                        "forecast_date": (last_date + timedelta(days=step)).isoformat(),
                        "predicted_units": round(avg, 2),
                    }
                )

        preds_df = pd.DataFrame(preds)
        run_id = save_run_and_predictions(
            con,
            split_date=str(last_date),
            horizon_days=horizon_days,
            chosen_model="FallbackMean",
            lr_m=ModelMetrics(0.0, 0.0, 0.0),
            rf_m=ModelMetrics(0.0, 0.0, 0.0),
            preds=preds_df,
        )

        fallback_conf = {
            "labels": ["LOW", "MEDIUM", "HIGH"],
            "matrix": [[0, 0, 0], [0, 0, 0], [0, 0, 0]],
            "bins": [0.0, 0.0],
        }
        return {
            "run_id": run_id,
            "chosen_model": "FallbackMean",
            "split_date": str(last_date),
            "horizon_days": horizon_days,
            "skus": int(preds_df["SKU_ID"].nunique()) if len(preds_df) else 0,
            "rows": int(len(preds_df)),
            "metrics": {"mae": 0.0, "rmse": 0.0, "r2": 0.0},
            "model_metrics": {
                "linear_regression": {"mae": 0.0, "rmse": 0.0, "r2": 0.0},
                "random_forest": {"mae": 0.0, "rmse": 0.0, "r2": 0.0},
            },
            "rf_confusion_matrix": fallback_conf,
            "predictions": preds_df.to_dict(orient="records"),
        }

    train, test, split_date = date_split(df_feat)

    roll_col = f"roll{used_roll}_mean"
    feature_cols = [f"lag_{l}" for l in used_lags] + [
        roll_col,
        "dow",
        "month",
        "Promotion_Flag",
        "Inventory_Level",
        "Reorder_Point",
        "Supplier_Lead_Time_Days",
        "Demand_Forecast",
    ]

    chosen_name, chosen_model, lr_m, rf_m, rf_conf = train_and_select(train, test, feature_cols)

    preds_df = iterative_forecast(
        chosen_model,
        df_ops,
        horizon_days=horizon_days,
        lags=used_lags,
        roll_window=used_roll,
    )

    if preds_df.empty:
        last_date = df_ops["Date"].max().date()
        preds = []
        for sku, g in df_ops.groupby("SKU_ID"):
            avg = float(g["Units_Sold"].mean()) if len(g) else 0.0
            for step in range(1, horizon_days + 1):
                preds.append(
                    {
                        "SKU_ID": sku,
                        "forecast_date": (last_date + timedelta(days=step)).isoformat(),
                        "predicted_units": round(avg, 2),
                    }
                )
        preds_df = pd.DataFrame(preds)
        chosen_name = "FallbackMean"

    run_id = save_run_and_predictions(con, split_date, horizon_days, chosen_name, lr_m, rf_m, preds_df)

    best_mae = min(lr_m.mae, rf_m.mae)
    best_rmse = min(lr_m.rmse, rf_m.rmse)
    best_r2 = max(lr_m.r2, rf_m.r2)

    return {
        "run_id": run_id,
        "chosen_model": chosen_name,
        "split_date": split_date,
        "horizon_days": horizon_days,
        "skus": int(preds_df["SKU_ID"].nunique()) if len(preds_df) else 0,
        "rows": int(len(preds_df)),
        "metrics": {
            "mae": round(best_mae, 3),
            "rmse": round(best_rmse, 3),
            "r2": round(best_r2, 3),
        },
        "model_metrics": {
            "linear_regression": {
                "mae": round(lr_m.mae, 3),
                "rmse": round(lr_m.rmse, 3),
                "r2": round(lr_m.r2, 3),
            },
            "random_forest": {
                "mae": round(rf_m.mae, 3),
                "rmse": round(rf_m.rmse, 3),
                "r2": round(rf_m.r2, 3),
            },
        },
        "rf_confusion_matrix": rf_conf,
        "predictions": preds_df.to_dict(orient="records"),
    }
