import argparse
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "supplychain.db"


def main():
    parser = argparse.ArgumentParser(description="Create low/out-of-stock demo rows in latest inventory snapshot")
    parser.add_argument("--low-stock", type=float, default=5.0, help="Inventory level for LOW examples")
    parser.add_argument("--out-stock", type=float, default=0.0, help="Inventory level for OUT examples")
    args = parser.parse_args()

    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()

        latest_date = cur.execute("SELECT MAX(Date) FROM daily_operations").fetchone()[0]
        if not latest_date:
            raise ValueError("daily_operations is empty")

        target_rows = cur.execute(
            """
            WITH latest AS (
                SELECT Date, SKU_ID, Warehouse_ID, ROW_NUMBER() OVER (ORDER BY SKU_ID, Warehouse_ID) AS rn
                FROM daily_operations
                WHERE Date = ?
                GROUP BY Date, SKU_ID, Warehouse_ID
            )
            SELECT SKU_ID, Warehouse_ID, rn
            FROM latest
            WHERE rn <= 6
            ORDER BY rn
            """,
            (latest_date,),
        ).fetchall()

        if len(target_rows) < 6:
            raise ValueError("Need at least 6 sku+warehouse combinations on latest date")

        for sku, wh, rn in target_rows:
            new_level = args.low_stock if rn <= 3 else args.out_stock
            cur.execute(
                """
                UPDATE daily_operations
                SET Inventory_Level = ?
                WHERE Date = ? AND SKU_ID = ? AND Warehouse_ID = ?
                """,
                (new_level, latest_date, sku, wh),
            )

        con.commit()
        print(f"Updated latest date: {latest_date}")
        print("Rows 1-3 set as LOW inventory, rows 4-6 set as OUT inventory.")
    finally:
        con.close()


if __name__ == "__main__":
    main()
