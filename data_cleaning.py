"""
data_cleaning.py
------------------
Day 2: Clean the raw CSVs in data/raw/ and write cleaned versions to
data/processed/.

Specific cleaning rules are applied to three files (matched by filename
keyword OR by column shape, so it still works if your filenames differ):

  nav_history            -> clean_nav_history()
  investor_transactions  -> clean_investor_transactions()
  scheme_performance     -> clean_scheme_performance()

Every other CSV gets a generic clean (drop exact duplicates, parse any
column with "date" in its name) so all 10 source files end up with a
cleaned counterpart in data/processed/.

ASSUMPTIONS ABOUT COLUMN NAMES (since the real files weren't available
when this was written) -- adjust the `find_col(...)` candidate lists
below if your actual headers differ:

  nav_history.csv:            amfi_code, date, nav
  investor_transactions.csv:  amfi_code, date, transaction_type, amount,
                               kyc_status, (optionally investor_id, state)
  scheme_performance.csv:     amfi_code, expense_ratio, and one or more
                               return_* / *_1y / *_3y / *_5y columns,
                               optionally an aum column and a date column

Usage:
    python data_cleaning.py
    python data_cleaning.py --raw-dir data/raw --out-dir data/processed
"""

import argparse
import glob
import os

import pandas as pd

KYC_ALLOWED = {"Verified", "Pending", "Rejected"}

TRANSACTION_TYPE_MAP = {
    "sip": "SIP",
    "systematic investment plan": "SIP",
    "lumpsum": "Lumpsum",
    "lump sum": "Lumpsum",
    "one time": "Lumpsum",
    "redemption": "Redemption",
    "redeem": "Redemption",
    "withdrawal": "Redemption",
}


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def find_col(df, candidates):
    """Case-insensitive match of the first matching column name."""
    lower_map = {c.strip().lower(): c for c in df.columns}
    for cand in candidates:
        if cand in lower_map:
            return lower_map[cand]
    return None


def parse_dates(series):
    return pd.to_datetime(series, errors="coerce", dayfirst=True)


def generic_clean(df):
    before = len(df)
    df = df.drop_duplicates()
    for c in df.columns:
        if "date" in c.lower():
            df[c] = parse_dates(df[c])
    print(f"  generic clean: {before} -> {len(df)} rows (exact duplicates removed)")
    return df


# ---------------------------------------------------------------------------
# nav_history.csv
# ---------------------------------------------------------------------------

def clean_nav_history(df):
    code_col = find_col(df, ["amfi_code", "scheme_code", "amficode", "code"])
    date_col = find_col(df, ["date", "nav_date"])
    nav_col = find_col(df, ["nav", "nav_value"])

    if not all([code_col, date_col, nav_col]):
        raise ValueError(
            f"nav_history.csv is missing an expected column. Found columns: {list(df.columns)}"
        )

    df = df.rename(columns={code_col: "amfi_code", date_col: "date", nav_col: "nav"})
    before = len(df)

    df["date"] = parse_dates(df["date"])
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")

    # treat non-positive NAV as missing too, so it gets corrected by ffill
    # below rather than just dropped outright
    n_nonpositive = int((df["nav"] <= 0).sum())
    df.loc[df["nav"] <= 0, "nav"] = pd.NA

    # sort + drop duplicate (amfi_code, date) rows, keep the first occurrence
    df = df.sort_values(["amfi_code", "date"]).reset_index(drop=True)
    dup_mask = df.duplicated(subset=["amfi_code", "date"], keep="first")
    n_dupes = int(dup_mask.sum())
    df = df[~dup_mask]

    # reindex each fund onto a continuous daily calendar (its own min..max
    # date) so weekends/holidays -- which simply don't appear as rows in
    # the source data -- get an explicit row, then forward-fill NAV into
    # those new rows from the last known trading-day value
    filled_parts = []
    n_filled_gaps = 0
    for code, grp in df.groupby("amfi_code"):
        grp = grp.set_index("date").sort_index()
        full_range = pd.date_range(grp.index.min(), grp.index.max(), freq="D")
        n_filled_gaps += len(full_range) - len(grp)
        grp = grp.reindex(full_range)
        grp["amfi_code"] = code
        grp["nav"] = grp["nav"].ffill()
        grp.index.name = "date"
        filled_parts.append(grp.reset_index())
    df = pd.concat(filled_parts, ignore_index=True)

    # anything still null (e.g. a fund's very first recorded day was itself
    # invalid, so there's nothing earlier to ffill from) gets dropped
    invalid_mask = df["nav"].isna() | (df["nav"] <= 0)
    n_invalid = int(invalid_mask.sum())
    df = df[~invalid_mask]

    print(f"  nav_history: {before} -> {len(df)} rows "
          f"(removed {n_dupes} duplicate amfi_code+date rows, "
          f"{n_nonpositive} non-positive NAV values treated as missing, "
          f"filled {n_filled_gaps} weekend/holiday gap-days via forward-fill, "
          f"dropped {n_invalid} rows still unfillable)")
    return df.sort_values(["amfi_code", "date"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# investor_transactions.csv
# ---------------------------------------------------------------------------

def clean_investor_transactions(df):
    code_col = find_col(df, ["amfi_code", "scheme_code"])
    type_col = find_col(df, ["transaction_type", "txn_type", "type"])
    amount_col = find_col(df, ["amount", "transaction_amount", "amt", "amount_inr"])
    date_col = find_col(df, ["date", "transaction_date", "txn_date"])
    kyc_col = find_col(df, ["kyc_status", "kyc"])

    rename_map = {}
    for col, new in [(code_col, "amfi_code"), (type_col, "transaction_type"),
                      (amount_col, "amount"), (date_col, "date"), (kyc_col, "kyc_status")]:
        if col:
            rename_map[col] = new
    df = df.rename(columns=rename_map)

    before = len(df)

    if "transaction_type" in df.columns:
        normalized = df["transaction_type"].astype(str).str.strip().str.lower().map(TRANSACTION_TYPE_MAP)
        unknown = normalized.isna() & df["transaction_type"].notna()
        df["transaction_type"] = normalized.where(~unknown, df["transaction_type"])
        if unknown.any():
            bad_vals = sorted(df.loc[unknown, "transaction_type"].astype(str).unique().tolist())
            print(f"  WARNING: unrecognized transaction_type values left as-is: {bad_vals}")

    n_bad_amount = 0
    if "amount" in df.columns:
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        bad_amount_mask = df["amount"].isna() | (df["amount"] <= 0)
        n_bad_amount = int(bad_amount_mask.sum())
        df = df[~bad_amount_mask]

    if "date" in df.columns:
        df["date"] = parse_dates(df["date"])

    n_bad_kyc = 0
    if "kyc_status" in df.columns:
        bad_kyc_mask = ~df["kyc_status"].astype(str).str.strip().isin(KYC_ALLOWED)
        n_bad_kyc = int(bad_kyc_mask.sum())
        if n_bad_kyc:
            bad_vals = sorted(df.loc[bad_kyc_mask, "kyc_status"].astype(str).unique().tolist())
            print(f"  WARNING: {n_bad_kyc} rows have a kyc_status outside {sorted(KYC_ALLOWED)}: {bad_vals}")

    before_dedupe = len(df)
    df = df.drop_duplicates()
    n_dupes = before_dedupe - len(df)

    print(f"  investor_transactions: {before} -> {len(df)} rows "
          f"(removed {n_bad_amount} rows with invalid amount, {n_dupes} duplicate rows; "
          f"flagged {n_bad_kyc} rows with unexpected kyc_status)")
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# scheme_performance.csv
# ---------------------------------------------------------------------------

def clean_scheme_performance(df):
    code_col = find_col(df, ["amfi_code", "scheme_code"])
    expense_col = find_col(df, ["expense_ratio", "ter", "expense_ratio_pct"])

    rename_map = {}
    if code_col:
        rename_map[code_col] = "amfi_code"
    if expense_col:
        rename_map[expense_col] = "expense_ratio"
    df = df.rename(columns=rename_map)

    before = len(df)

    return_cols = [c for c in df.columns
                   if "return" in c.lower() or any(tag in c.lower() for tag in ("1y", "3y", "5y"))]
    n_non_numeric = 0
    for c in return_cols:
        coerced = pd.to_numeric(df[c], errors="coerce")
        n_non_numeric += int((coerced.isna() & df[c].notna()).sum())
        df[c] = coerced

    n_out_of_range = 0
    if "expense_ratio" in df.columns:
        df["expense_ratio"] = pd.to_numeric(df["expense_ratio"], errors="coerce")
        out_of_range = ~df["expense_ratio"].between(0.1, 2.5)
        n_out_of_range = int(out_of_range.sum())
        if n_out_of_range:
            print(f"  WARNING: {n_out_of_range} rows have expense_ratio outside the "
                  f"expected 0.1%-2.5% range")

    n_return_anomalies = 0
    for c in return_cols:
        anomaly = df[c].abs() > 100  # a >100% magnitude annualized return is suspicious
        n_return_anomalies += int(anomaly.sum())
    if n_return_anomalies:
        print(f"  WARNING: {n_return_anomalies} suspicious return values "
              f"(>100% magnitude) across columns {return_cols}")

    before_dedupe = len(df)
    df = df.drop_duplicates()
    n_dupes = before_dedupe - len(df)

    print(f"  scheme_performance: {before} -> {len(df)} rows "
          f"(removed {n_dupes} duplicate rows; flagged {n_non_numeric} non-numeric "
          f"return values, {n_out_of_range} out-of-range expense ratios, "
          f"{n_return_anomalies} return anomalies)")
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

HANDLERS = [
    (["nav_history", "nav history"], clean_nav_history),
    (["investor_transactions", "transactions"], clean_investor_transactions),
    (["scheme_performance", "performance"], clean_scheme_performance),
]


def main():
    parser = argparse.ArgumentParser(description="Day 2 data cleaning")
    parser.add_argument("--raw-dir", default="data/raw")
    parser.add_argument("--out-dir", default="data/processed")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    files = sorted(glob.glob(os.path.join(args.raw_dir, "*.csv")))

    print(f"Found {len(files)} CSV file(s) in {args.raw_dir}\n")

    for path in files:
        name = os.path.basename(path)
        df = pd.read_csv(path)
        print(f"Cleaning {name} ...")

        handler = generic_clean
        for keywords, fn in HANDLERS:
            if any(k in name.lower() for k in keywords):
                handler = fn
                break

        try:
            cleaned = handler(df)
        except Exception as e:
            print(f"  ERROR applying specific cleaning to {name}: {e}")
            print("  Falling back to generic clean for this file.")
            cleaned = generic_clean(df)

        out_path = os.path.join(args.out_dir, name)
        cleaned.to_csv(out_path, index=False)
        print(f"  Saved -> {out_path}\n")

    print("Done.")


if __name__ == "__main__":
    main()