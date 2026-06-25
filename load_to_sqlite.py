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
    return pd.to_datetime(series, errors="coerce").dt.strftime("%Y%m%d").astype("Int64")


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
        if "date" in fact_txn.columns:
            fact_txn["date_id"] = to_date_id(fact_txn["date"])
        keep = [c for c in
                ["amfi_code", "date_id", "investor_id", "transaction_type", "amount", "kyc_status",
                 "state", "city", "city_tier", "age_group", "gender", "annual_income_lakh", "payment_mode"]
                if c in fact_txn.columns]
        fact_txn = fact_txn[keep]
        if "date_id" in fact_txn.columns:
            fact_txn = fact_txn.dropna(subset=["date_id"])
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

        # Only rename columns that actually start with "return" -- matching on
        # a bare "1y"/"3y"/"5y" substring is too loose and can catch unrelated
        # columns like "benchmark_3yr_pct", which would collide with return_3y.
        rename_returns = {}
        for c in perf.columns:
            cl = c.lower()
            if not cl.startswith("return"):
                continue
            if "1y" in cl:
                rename_returns[c] = "return_1y"
            elif "3y" in cl:
                rename_returns[c] = "return_3y"
            elif "5y" in cl:
                rename_returns[c] = "return_5y"
        perf = perf.rename(columns=rename_returns)

        # Fund-descriptor columns belong in dim_fund, not a performance fact row.
        DESCRIPTIVE_COLS = {"scheme_name", "fund_house", "category", "sub_category",
                             "plan", "risk_grade"}

        aum_col = find_col(perf, ["aum", "aum_cr", "aum_crore"])

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