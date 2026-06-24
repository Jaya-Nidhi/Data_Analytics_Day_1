"""
data_ingestion.py
------------------
Day 1: Data ingestion for the Mutual Fund Analytics project.

What this script does (maps to the Day 1 task list):
1. Loads every CSV found in data/raw/ with pandas.
2. Prints .shape, .dtypes and .head() for each, and flags basic anomalies
   (nulls, duplicates, suspicious dtypes, negative/zero NAVs, etc).
3. If a "fund master" file is found, prints unique fund houses, categories,
   sub-categories and risk grades, and explains the AMFI scheme-code structure.
4. If both a fund-master and a nav-history file are found, validates that
   every AMFI scheme code in the master exists in the NAV history.
5. Writes a short data-quality summary to reports/data_quality_summary.md.

Usage:
    python data_ingestion.py
    python data_ingestion.py --data-dir data/raw --report-dir reports
"""

import argparse
import glob
import os
from datetime import datetime

import pandas as pd


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_csv_files(data_dir):
    files = sorted(glob.glob(os.path.join(data_dir, "*.csv")))
    if not files:
        print(f"No CSV files found in '{data_dir}'. "
              f"Drop your 10 raw CSVs there and re-run.")
    return files


def guess_scheme_code_column(df):
    candidates = ["scheme_code", "schemecode", "amfi_code", "amficode", "code"]
    for col in df.columns:
        if col.strip().lower() in candidates:
            return col
    return None


def looks_like_fund_master(filename, df):
    name_hit = "master" in filename.lower() or "fund_master" in filename.lower()
    cols = [c.lower() for c in df.columns]
    col_hit = any("fund_house" in c or "amc" in c for c in cols) and \
        any("categor" in c for c in cols)
    return name_hit or col_hit


def looks_like_nav_history(filename, df):
    name_hit = "nav" in filename.lower() and "history" in filename.lower()
    cols = [c.lower() for c in df.columns]
    col_hit = any(c == "nav" or c.startswith("nav") for c in cols) and \
        any("date" in c for c in cols)
    return name_hit or col_hit


# ---------------------------------------------------------------------------
# Core profiling
# ---------------------------------------------------------------------------

def profile_dataframe(name, df, report_lines):
    print("\n" + "=" * 90)
    print(f"FILE: {name}")
    print("=" * 90)

    print(f"\nShape: {df.shape[0]} rows x {df.shape[1]} columns")
    print("\nDtypes:")
    print(df.dtypes)
    print("\nHead:")
    print(df.head())

    report_lines.append(f"\n### {name}")
    report_lines.append(f"- Shape: {df.shape[0]} rows x {df.shape[1]} columns")

    anomalies = []

    # 1. Nulls
    null_counts = df.isnull().sum()
    null_cols = null_counts[null_counts > 0]
    if not null_cols.empty:
        msg = "Null values found in: " + ", ".join(
            f"{c} ({n})" for c, n in null_cols.items()
        )
        anomalies.append(msg)

    # 2. Fully duplicated rows
    dup_count = df.duplicated().sum()
    if dup_count > 0:
        anomalies.append(f"{dup_count} fully duplicated rows")

    # 3. Duplicate scheme codes in a master table (should be unique per fund)
    code_col = guess_scheme_code_column(df)
    if code_col and looks_like_fund_master(name, df):
        dup_codes = df[code_col].duplicated().sum()
        if dup_codes > 0:
            anomalies.append(
                f"{dup_codes} duplicate values in scheme-code column '{code_col}' "
                f"(expected unique per fund in a master table)"
            )

    # 4. Negative or zero NAV values
    nav_cols = [c for c in df.columns if c.lower() == "nav" or c.lower().startswith("nav")]
    for nc in nav_cols:
        numeric_nav = pd.to_numeric(df[nc], errors="coerce")
        bad = (numeric_nav <= 0).sum()
        if bad > 0:
            anomalies.append(f"{bad} non-positive values in '{nc}' column")

    # 5. Columns that are entirely empty
    empty_cols = [c for c in df.columns if df[c].isnull().all()]
    if empty_cols:
        anomalies.append(f"Entirely empty columns: {', '.join(empty_cols)}")

    # 6. Object columns that are actually numeric (loaded as text)
    for c in df.select_dtypes(include=["object", "string"]).columns:
        coerced = pd.to_numeric(df[c], errors="coerce")
        if coerced.notna().mean() > 0.9 and df[c].notna().any():
            anomalies.append(
                f"Column '{c}' looks numeric but was loaded as text/object"
            )

    if anomalies:
        print("\nAnomalies detected:")
        for a in anomalies:
            print(f"  - {a}")
        report_lines.append("- Anomalies:")
        for a in anomalies:
            report_lines.append(f"  - {a}")
    else:
        print("\nNo obvious anomalies detected.")
        report_lines.append("- Anomalies: none detected")


def explore_fund_master(name, df, report_lines):
    print("\n" + "-" * 90)
    print(f"FUND MASTER EXPLORATION: {name}")
    print("-" * 90)

    cols = {c.lower(): c for c in df.columns}

    def show_unique(key_substrings, label):
        for key, original in cols.items():
            if any(sub in key for sub in key_substrings):
                vals = sorted(df[original].dropna().unique().tolist())
                print(f"\nUnique {label} ({len(vals)}): {vals}")
                report_lines.append(f"- Unique {label} ({len(vals)}): {vals}")
                return
        print(f"\nNo column found for {label}.")

    show_unique(["fund_house", "amc"], "fund houses")
    show_unique(["category"], "categories")
    show_unique(["sub_category", "subcategory"], "sub-categories")
    show_unique(["risk"], "risk grades")

    note = (
        "AMFI scheme codes are unique numeric identifiers (typically 5-6 digits) "
        "assigned by AMFI to every open-ended scheme/plan/option combination "
        "(e.g. Direct-Growth and Regular-Growth of the same fund get different "
        "codes). Codes are NOT permanent labels of a fund's identity: when a "
        "scheme merges, is renamed, or is wound up, its code can be reused or "
        "reassigned. Always cross-check the 'scheme_name' / 'fund_house' "
        "returned by the API against what you expect, rather than trusting "
        "the code alone."
    )
    print(f"\nAMFI scheme code structure note:\n  {note}")
    report_lines.append(f"- AMFI scheme code note: {note}")


def validate_codes(master_df, master_name, nav_df, nav_name, report_lines):
    master_code_col = guess_scheme_code_column(master_df)
    nav_code_col = guess_scheme_code_column(nav_df)

    print("\n" + "-" * 90)
    print(f"AMFI CODE VALIDATION: {master_name} vs {nav_name}")
    print("-" * 90)

    if not master_code_col or not nav_code_col:
        msg = ("Could not validate: scheme-code column not found in one or "
               "both files.")
        print(msg)
        report_lines.append(f"- {msg}")
        return

    master_codes = set(pd.to_numeric(master_df[master_code_col], errors="coerce").dropna())
    nav_codes = set(pd.to_numeric(nav_df[nav_code_col], errors="coerce").dropna())

    missing = master_codes - nav_codes
    pct_covered = 100 * (len(master_codes) - len(missing)) / max(len(master_codes), 1)

    print(f"Fund-master codes: {len(master_codes)}")
    print(f"Nav-history codes: {len(nav_codes)}")
    print(f"Coverage: {pct_covered:.1f}% of master codes have NAV history")

    report_lines.append(f"- Fund-master codes: {len(master_codes)}")
    report_lines.append(f"- Nav-history codes: {len(nav_codes)}")
    report_lines.append(f"- Coverage: {pct_covered:.1f}% of master codes have NAV history")

    if missing:
        sample = sorted(missing)[:20]
        print(f"Missing codes (no NAV history found), showing up to 20: {sample}")
        report_lines.append(f"- Missing codes (sample, up to 20): {sample}")
    else:
        print("All fund-master codes have matching NAV history.")
        report_lines.append("- All fund-master codes have matching NAV history.")


def main():
    parser = argparse.ArgumentParser(description="Day 1 data ingestion")
    parser.add_argument("--data-dir", default="data/raw")
    parser.add_argument("--report-dir", default="reports")
    args = parser.parse_args()

    os.makedirs(args.report_dir, exist_ok=True)

    csv_files = find_csv_files(args.data_dir)

    report_lines = [
        "# Data Quality Summary",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"\nFiles scanned: {len(csv_files)} (expected 10)",
    ]

    loaded = {}
    for path in csv_files:
        name = os.path.basename(path)
        try:
            df = pd.read_csv(path)
        except Exception as e:
            print(f"\nFailed to load {name}: {e}")
            report_lines.append(f"\n### {name}\n- FAILED TO LOAD: {e}")
            continue
        loaded[name] = df
        profile_dataframe(name, df, report_lines)

    master_name, master_df = None, None
    nav_name, nav_df = None, None
    for name, df in loaded.items():
        if master_name is None and looks_like_fund_master(name, df):
            master_name, master_df = name, df
        if nav_name is None and looks_like_nav_history(name, df):
            nav_name, nav_df = name, df

    if master_df is not None:
        explore_fund_master(master_name, master_df, report_lines)
    else:
        print("\nNo fund master file detected (expected a file with fund "
              "house / category columns).")

    if master_df is not None and nav_df is not None:
        validate_codes(master_df, master_name, nav_df, nav_name, report_lines)
    else:
        print("\nSkipping AMFI code validation: need both a fund-master "
              "and a nav-history file.")
        report_lines.append(
            "\n- AMFI code validation skipped: master and/or nav-history "
            "file not found among the loaded CSVs."
        )

    report_path = os.path.join(args.report_dir, "data_quality_summary.md")
    with open(report_path, "w") as f:
        f.write("\n".join(report_lines))
    print(f"\nData quality summary written to {report_path}")


if __name__ == "__main__":
    main()