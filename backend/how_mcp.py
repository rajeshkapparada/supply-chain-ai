import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).parent / "supplychain.db"


def main():
    con = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(
            """
            SELECT id, created_at, run_id, day, sku, warehouse,
                   recommended_action, recommended_qty, status
            FROM mcp_decisions
            ORDER BY id DESC
            LIMIT 20
            """,
            con,
        )
        print(df)
    finally:
        con.close()


if __name__ == "__main__":
    main()
