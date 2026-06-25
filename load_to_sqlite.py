"""
load_to_sqlite.py
------------------
Day 2: Build bluestock_mf.db from schema.sql, then load the cleaned CSVs
in data/processed/ into the star schema using SQLAlchemy + df.to_sql().

Run data_cleaning.py first so data/processed/ is populated.

Usage:
    python load_to_sqlite.py
"""

import glob
import os
import sqlite3

import pandas as pd
from sqlalchemy import create_engine

PROCESSED_DIR = "data/processed"
DB_PATH = "bluestock_mf.db"
SCHEMA_PATH = "schema.sql"


def find_col(df, candidates):
    lower_map = {c.strip().lower(): c for c in df.columns}
    for cand in candidates:
        if cand in lower_map:
            return lower_map[cand]
    return None


def load_csv_if_exists(name_keywords):
    for f in glob.glob(os.path.join(PROCESSED_DIR, "*.csv")):
        if any(k in os.path.basename(f).lower() for k in name_keywords):
            return pd.read_csv(f)
    return None


def build_dim_date(all_dates):
    dates = pd.to_datetime(pd.Series(all_dates).dropna().unique())
    dim = pd.DataFrame({"full_date": dates})
    dim["date_id"] = dim["full_date"].dt.strftime("%Y%m%d").astype(int)
    dim["year"] = dim["full_date"].dt.year
    dim["quarter"] = dim["full_date"].dt.quarter
    dim["month"] = dim["full_date"].dt.month
    dim["month_name"] = dim["full_date"].dt.month_name()
    dim["day"] = dim["full_date"].dt.day
    dim["day_of_week"] = dim["full_date"].dt.day_name()
    dim["is_weekend"] = dim["day_of_week"].isin(["Saturday", "Sunday"]).astype(int)
    dim["full_date"] = dim["full_date"].dt.strftime("%Y-%m-%d")
    return dim.drop_duplicates(subset=["date_id"]).sort_values("date_id").reset_index(drop=True)


def to_date_id(series):
    # Use ISO8601 format first to avoid the pandas 3.x dayfirst corruption bug
    # (dayfirst=True silently swaps month/day for DD<=12 on YYYY-MM-DD strings).
    parsed = pd.to_datetime(series, errors="coerce", format="ISO8601")
    # Retry any genuinely non-ISO values without dayfirst
    unparsed = parsed.isna() & pd.Series(series).notna()
    if unparsed.any():
        parsed[unparsed] = pd.to_datetime(series[unparsed], errors="coerce", dayfirst=False)
    return parsed.dt.strftime("%Y%m%d").astype("Int64")


def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    # Create all tables/indexes from schema.sql first, then append rows into them.
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())
    conn.close()

    engine = create_engine(f"sqlite:///{DB_PATH}")

    nav_df = load_csv_if_exists(["nav_history"])
    txn_df = load_csv_if_exists(["investor_transactions", "transactions"])
    perf_df = load_csv_if_exists(["scheme_performance", "performance"])
    master_df = load_csv_if_exists(["fund_master", "master"])

    if nav_df is None:
        raise SystemExit(
            "No cleaned nav_history CSV found in data/processed/. "
            "Run data_cleaning.py first."
        )

    # ---- dim_date: union of every date across all fact sources ----
    # scheme_performance.csv may be a single point-in-time snapshot with no
    # date column at all -- in that case we tag every row with today's date
    # as the "as of" date, so it still has somewhere to live in dim_date.
    SNAPSHOT_DATE = pd.Timestamp.now().normalize()

    all_dates = list(pd.to_datetime(nav_df.get("date"), errors="coerce"))
    if txn_df is not None and "date" in txn_df.columns:
        all_dates += list(pd.to_datetime(txn_df["date"], errors="coerce"))
    if perf_df is not None:
        perf_date_col = find_col(perf_df, ["date"])
        if perf_date_col:
            all_dates += list(pd.to_datetime(perf_df[perf_date_col], errors="coerce"))
        else:
            all_dates.append(SNAPSHOT_DATE)
            print(f"No date column found in scheme_performance.csv -- treating it as a "
                  f"single snapshot and tagging all its rows with today's date "
                  f"({SNAPSHOT_DATE.date()}) as the as-of date.")

    dim_date = build_dim_date(all_dates)
    dim_date.to_sql("dim_date", engine, if_exists="append", index=False)

    # ---- dim_fund ----
    if master_df is not None:
        code_col = find_col(master_df, ["amfi_code", "scheme_code"])
        dim_fund = master_df.rename(columns={code_col: "amfi_code"})
        # fund_master.csv uses 'risk_category'; the schema column is 'risk_grade'.
        # Rename so the data actually lands in the DB instead of being silently dropped.
        risk_col = find_col(dim_fund, ["risk_category", "risk_grade"])
        if risk_col and risk_col != "risk_grade":
            dim_fund = dim_fund.rename(columns={risk_col: "risk_grade"})
        keep = [c for c in
                ["amfi_code", "fund_house", "scheme_name", "category", "sub_category", "risk_grade"]
                if c in dim_fund.columns]
        dim_fund = dim_fund[keep].drop_duplicates(subset=["amfi_code"])
    else:
        print("No fund_master CSV found -- building a minimal dim_fund from "
              "the amfi_codes seen in nav_history.")
        code_col = find_col(nav_df, ["amfi_code", "scheme_code"])
        dim_fund = pd.DataFrame({"amfi_code": nav_df[code_col].dropna().unique()})

    dim_fund.to_sql("dim_fund", engine, if_exists="append", index=False)

    # ---- fact_nav ----
    code_col = find_col(nav_df, ["amfi_code", "scheme_code"])
    fact_nav = nav_df.rename(columns={code_col: "amfi_code"})[["amfi_code", "date", "nav"]].copy()
    fact_nav["date_id"] = to_date_id(fact_nav["date"])
    fact_nav = fact_nav.drop(columns=["date"]).dropna(subset=["date_id"])
    fact_nav.to_sql("fact_nav", engine, if_exists="append", index=False)

    # ---- fact_transactions ----
    fact_txn = pd.DataFrame()
    if txn_df is not None:
        code_col = find_col(txn_df, ["amfi_code", "scheme_code"])
        fact_txn = txn_df.rename(columns={code_col: "amfi_code"}).copy()

        # The raw CSV uses 'transaction_date' and 'amount_inr'; data_cleaning.py renames
        # these to 'date' and 'amount'. Handle both so this works whether or not
        # data_cleaning was run first.
        date_col = find_col(fact_txn, ["date", "transaction_date", "txn_date"])
        if date_col and date_col != "date":
            fact_txn = fact_txn.rename(columns={date_col: "date"})
        amount_col = find_col(fact_txn, ["amount", "amount_inr", "transaction_amount", "amt"])
        if amount_col and amount_col != "amount":
            fact_txn = fact_txn.rename(columns={amount_col: "amount"})

        if "date" in fact_txn.columns:
            fact_txn["date_id"] = to_date_id(fact_txn["date"])
        keep = [c for c in
                ["amfi_code", "date_id", "investor_id", "transaction_type", "amount", "kyc_status",
                 "state", "city", "city_tier", "age_group", "gender", "annual_income_lakh", "payment_mode"]
                if c in fact_txn.columns]
        fact_txn = fact_txn[keep]
        if "date_id" in fact_txn.columns:
            # Instead of silently dropping rows whose date couldn't be parsed, use a
            # sentinel date_id of 19000101 so the row is preserved and queryable.
            # A missing transaction date is a data-quality issue, not a reason to lose the record.
            SENTINEL_DATE_ID = 19000101
            null_date_mask = fact_txn["date_id"].isna()
            n_null_dates = int(null_date_mask.sum())
            if n_null_dates:
                print(f"  WARNING: {n_null_dates} transaction rows have an unparseable date -- "
                      f"assigned sentinel date_id {SENTINEL_DATE_ID} so the rows are preserved.")
                fact_txn["date_id"] = fact_txn["date_id"].fillna(SENTINEL_DATE_ID).astype(int)
                # Ensure the sentinel date exists in dim_date
                sentinel_row = pd.DataFrame([{
                    "date_id": SENTINEL_DATE_ID, "full_date": "1900-01-01",
                    "year": 1900, "quarter": 1, "month": 1, "month_name": "January",
                    "day": 1, "day_of_week": "Monday", "is_weekend": 0,
                }])
                sentinel_row.to_sql("dim_date", engine, if_exists="append", index=False)
        fact_txn.to_sql("fact_transactions", engine, if_exists="append", index=False)
    else:
        print("No investor_transactions CSV found -- fact_transactions left empty.")

    # ---- fact_performance + fact_aum ----
    fact_perf = pd.DataFrame()
    fact_aum = pd.DataFrame()
    if perf_df is not None:
        code_col = find_col(perf_df, ["amfi_code", "scheme_code"])
        perf = perf_df.rename(columns={code_col: "amfi_code"}).copy()

        date_col = find_col(perf, ["date"])
        if date_col:
            perf["date_id"] = to_date_id(perf[date_col])
        else:
            perf["date_id"] = int(SNAPSHOT_DATE.strftime("%Y%m%d"))

        # Rename return_*yr_pct / return_*y to the canonical schema names.
        # Handles both '1yr' (return_1yr_pct) and '1y' (return_1y) style suffixes.
        rename_returns = {}
        for c in perf.columns:
            cl = c.lower()
            if not cl.startswith("return"):
                continue
            if "1yr" in cl or ("1y" in cl and "1yr" not in cl):
                rename_returns[c] = "return_1y"
            elif "3yr" in cl or ("3y" in cl and "3yr" not in cl):
                rename_returns[c] = "return_3y"
            elif "5yr" in cl or ("5y" in cl and "5yr" not in cl):
                rename_returns[c] = "return_5y"
        perf = perf.rename(columns=rename_returns)

        # Fund-descriptor columns belong in dim_fund, not a performance fact row.
        DESCRIPTIVE_COLS = {"scheme_name", "fund_house", "category", "sub_category",
                             "plan", "risk_grade"}

        aum_col = find_col(perf, ["aum_cr", "aum_crore", "aum"])

        # Known performance/risk metric columns we have a schema.sql slot for.
        # If your real file has even more metric columns, add the column name
        # here AND a matching line in schema.sql's fact_performance table.
        PERF_METRIC_COLS = {
            "return_1y", "return_3y", "return_5y", "expense_ratio",
            "alpha", "beta", "sharpe_ratio", "sortino_ratio",
            "std_dev_ann_pct", "max_drawdown_pct", "benchmark_3yr_pct",
            "morningstar_rating",
        }

        perf_keep = ["amfi_code", "date_id"] + [c for c in perf.columns if c in PERF_METRIC_COLS]
        fact_perf = perf[perf_keep].copy()
        fact_perf = fact_perf.dropna(subset=["date_id"])
        fact_perf.to_sql("fact_performance", engine, if_exists="append", index=False)

        dropped = [c for c in perf.columns
                   if c not in perf_keep and c not in DESCRIPTIVE_COLS
                   and c != aum_col and c != date_col]
        if dropped:
            print(f"Note: columns not loaded into fact_performance (no schema.sql slot "
                  f"defined yet): {dropped}")

        if aum_col:
            fact_aum = perf[["amfi_code", "date_id", aum_col]].rename(columns={aum_col: "aum_cr"})
            fact_aum = fact_aum.dropna(subset=["date_id", "aum_cr"])
            fact_aum.to_sql("fact_aum", engine, if_exists="append", index=False)
        else:
            print("No AUM column found in scheme_performance -- fact_aum left empty.")
    else:
        print("No scheme_performance CSV found -- fact_performance/fact_aum left empty.")

    # ---- fact_portfolio_holdings ----
    holdings_df = load_csv_if_exists(["portfolio_holdings", "holdings"])
    if holdings_df is not None:
        holdings_df["date_id"] = to_date_id(holdings_df.get("portfolio_date",
                                             holdings_df.get("date", None)))
        # Ensure all portfolio dates exist in dim_date
        extra_dates = build_dim_date(
            pd.to_datetime(holdings_df.get("portfolio_date",
                           holdings_df.get("date")), errors="coerce").dropna().unique()
        )
        extra_dates = extra_dates[~extra_dates["date_id"].isin(
            pd.read_sql("SELECT date_id FROM dim_date", engine)["date_id"]
        )]
        if not extra_dates.empty:
            extra_dates.to_sql("dim_date", engine, if_exists="append", index=False)

        hold_keep = [c for c in
                     ["amfi_code", "date_id", "stock_symbol", "stock_name",
                      "sector", "weight_pct", "market_value_cr", "current_price_inr"]
                     if c in holdings_df.columns]
        holdings_df[hold_keep].dropna(subset=["date_id"]).to_sql(
            "fact_portfolio_holdings", engine, if_exists="append", index=False)
        print(f"  fact_portfolio_holdings: loaded {len(holdings_df)} rows")
    else:
        print("No portfolio_holdings CSV found -- fact_portfolio_holdings left empty.")

    # ---- dim_benchmark / fact_benchmark_prices ----
    bench_df = load_csv_if_exists(["benchmark_indices", "benchmark"])
    if bench_df is not None:
        bench_df["date_id"] = to_date_id(bench_df["date"])
        # Add any benchmark dates missing from dim_date
        extra_dates = build_dim_date(
            pd.to_datetime(bench_df["date"], errors="coerce").dropna().unique()
        )
        extra_dates = extra_dates[~extra_dates["date_id"].isin(
            pd.read_sql("SELECT date_id FROM dim_date", engine)["date_id"]
        )]
        if not extra_dates.empty:
            extra_dates.to_sql("dim_date", engine, if_exists="append", index=False)

        bench_df.drop(columns=["date"], errors="ignore").dropna(subset=["date_id"]).to_sql(
            "fact_benchmark_prices", engine, if_exists="append", index=False)
        print(f"  fact_benchmark_prices: loaded {len(bench_df)} rows")
    else:
        print("No benchmark_indices CSV found -- fact_benchmark_prices left empty.")

    # ---- verification: cleaned (processed) CSV rows vs rows actually loaded ----
    print("\nRow count verification (cleaned CSV rows -> rows loaded into fact table):")
    print(f"  nav_history           -> fact_nav:          {len(nav_df):>6} -> {len(fact_nav):>6}")
    if txn_df is not None:
        print(f"  investor_transactions -> fact_transactions: {len(txn_df):>6} -> {len(fact_txn):>6}")
    if perf_df is not None:
        print(f"  scheme_performance    -> fact_performance:  {len(perf_df):>6} -> {len(fact_perf):>6}")
        print(f"  scheme_performance    -> fact_aum:           {len(perf_df):>6} -> {len(fact_aum):>6}")

    print(f"\nSQLite database written to {DB_PATH}")


if __name__ == "__main__":
    main()