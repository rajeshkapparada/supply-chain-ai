# Demo Steps (End-to-End)

## 1) Start backend

```powershell
cd C:\Users\kappa\Downloads\supplychain-ai\backend
python db.py --init --load-csv data/daily_operations.csv
python app.py
```

After every `POST /forecast/run`, terminal prints:

- LR: MAE, RMSE, R2
- RF: MAE, RMSE, R2
- chosen model

## 2) Start frontend

```powershell
cd C:\Users\kappa\Downloads\supplychain-ai\frontend
npm install
npm run dev
```

Open: `http://localhost:5173`

## 3) Manual low-stock / out-of-stock demo (professor question)

### Option A (recommended script)

```powershell
cd C:\Users\kappa\Downloads\supplychain-ai\backend
python manual_inventory_adjust.py --low-stock 4 --out-stock 0
```

What it does:
- Finds latest date in `daily_operations`
- Sets 3 sku/warehouse rows to low stock
- Sets 3 sku/warehouse rows to out of stock

Then in UI:
1. Open **Feature 2: Inventory**
2. Click **Run Forecast + MCP**
3. Check `LOW` and `OUT` statuses + `REORDER` actions
4. Check **MCP decision history** table (saved rows in SQLite)

### Option B (manual SQL)

Run this in DB Browser for SQLite / sqlite shell:

```sql
UPDATE daily_operations
SET Inventory_Level = 3
WHERE Date = (SELECT MAX(Date) FROM daily_operations)
  AND SKU_ID IN (
    SELECT SKU_ID FROM daily_operations
    WHERE Date = (SELECT MAX(Date) FROM daily_operations)
    LIMIT 3
  );

UPDATE daily_operations
SET Inventory_Level = 0
WHERE Date = (SELECT MAX(Date) FROM daily_operations)
  AND SKU_ID IN (
    SELECT SKU_ID FROM daily_operations
    WHERE Date = (SELECT MAX(Date) FROM daily_operations)
    LIMIT 3 OFFSET 3
  );
```

## 4) Forecasting scenario checks (simple presentation flow)

Use Feature 1 and run 3 scenarios:

1. Baseline: horizon = 7
2. Medium horizon: horizon = 14
3. Long horizon: horizon = 30

For each run, note:
- terminal metrics (LR/RF MAE, RMSE, R2)
- chosen model
- confusion matrix (RF)

### Data-change scenario test (optional)

To force visible behavior difference, temporarily alter recent demand:

```sql
UPDATE daily_operations
SET Units_Sold = Units_Sold * 1.25
WHERE Date >= date((SELECT MAX(Date) FROM daily_operations), '-14 day');
```

Run forecast again and compare metrics/predictions.

To revert, reload CSV:

```powershell
python db.py --init --load-csv data/daily_operations.csv
```

## 5) MCP + Agent explanation (for viva)

- Inventory Agent uses MCP client/server/tools pattern.
- Agent calls MCP tools to fetch inventory/forecast context, then computes reorder decisions.
- MCP is transport/tooling layer, not the business decision-maker by itself.

- Supplier Reliability Agent is separate and does not require MCP.
- Inventory Agent uses supplier scores as an input signal; communication happens through shared data/API outputs, not direct agent-to-agent chat.

## 6) Where results are visible

- Forecast metrics + confusion matrix: **Feature 1 UI**
- Forecast metrics in terminal: backend terminal (on `/forecast/run`)
- MCP decisions latest + history: **Feature 2 UI**
- Supplier scores: **Feature 3 UI**
- Region demand: **Feature 4 UI**
- Promotion uplift + stockout analytics: **Feature 5 UI**
