# Data Quality Summary
Generated: 2026-06-24 12:17

Files scanned: 18 (expected 10)

### 01_fund_master.csv
- Shape: 40 rows x 15 columns
- Anomalies: none detected

### 02_nav_history.csv
- Shape: 46000 rows x 3 columns
- Anomalies: none detected

### 03_aum_by_fund_house.csv
- Shape: 90 rows x 5 columns
- Anomalies: none detected

### 04_monthly_sip_inflows.csv
- Shape: 48 rows x 6 columns
- Anomalies:
  - Null values found in: yoy_growth_pct (12)

### 05_category_inflows.csv
- Shape: 144 rows x 3 columns
- Anomalies: none detected

### 06_industry_folio_count.csv
- Shape: 21 rows x 6 columns
- Anomalies: none detected

### 07_scheme_performance.csv
- Shape: 40 rows x 19 columns
- Anomalies: none detected

### 08_investor_transactions.csv
- Shape: 32778 rows x 13 columns
- Anomalies: none detected

### 09_portfolio_holdings.csv
- Shape: 322 rows x 8 columns
- Anomalies: none detected

### 10_benchmark_indices.csv
- Shape: 8050 rows x 3 columns
- Anomalies: none detected

### live_nav_fetch_summary.csv
- Shape: 6 rows x 7 columns
- Anomalies: none detected

### nav_axis_bluechip_119092.csv
- Shape: 3581 rows x 6 columns
- Anomalies:
  - 3580 duplicate values in scheme-code column 'scheme_code' (expected unique per fund in a master table)

### nav_hdfc_top_100_direct_125497.csv
- Shape: 3107 rows x 6 columns
- Anomalies:
  - 3106 duplicate values in scheme-code column 'scheme_code' (expected unique per fund in a master table)

### nav_icici_bluechip_120503.csv
- Shape: 3323 rows x 6 columns
- Anomalies:
  - 3322 duplicate values in scheme-code column 'scheme_code' (expected unique per fund in a master table)
  - 1 non-positive values in 'nav' column

### nav_kotak_bluechip_120841.csv
- Shape: 3317 rows x 6 columns
- Anomalies:
  - 3316 duplicate values in scheme-code column 'scheme_code' (expected unique per fund in a master table)

### nav_nippon_large_cap_118632.csv
- Shape: 3314 rows x 6 columns
- Anomalies:
  - 3313 duplicate values in scheme-code column 'scheme_code' (expected unique per fund in a master table)

### nav_sbi_bluechip.csv
- Shape: 3252 rows x 3 columns
- Anomalies: none detected

### nav_sbi_bluechip_119551.csv
- Shape: 3252 rows x 6 columns
- Anomalies:
  - 3251 duplicate values in scheme-code column 'scheme_code' (expected unique per fund in a master table)
- Unique fund houses (10): ['Aditya Birla Sun Life MF', 'Axis Mutual Fund', 'DSP Mutual Fund', 'HDFC Mutual Fund', 'ICICI Prudential MF', 'Kotak Mahindra MF', 'Mirae Asset MF', 'Nippon India MF', 'SBI Mutual Fund', 'UTI Mutual Fund']
- Unique categories (2): ['Debt', 'Equity']
- Unique sub-categories (12): ['ELSS', 'Flexi Cap', 'Gilt', 'Index', 'Index/ETF', 'Large & Mid Cap', 'Large Cap', 'Liquid', 'Mid Cap', 'Short Duration', 'Small Cap', 'Value']
- Unique risk grades (5): ['High', 'Low', 'Moderate', 'Moderately High', 'Very High']
- AMFI scheme code note: AMFI scheme codes are unique numeric identifiers (typically 5-6 digits) assigned by AMFI to every open-ended scheme/plan/option combination (e.g. Direct-Growth and Regular-Growth of the same fund get different codes). Codes are NOT permanent labels of a fund's identity: when a scheme merges, is renamed, or is wound up, its code can be reused or reassigned. Always cross-check the 'scheme_name' / 'fund_house' returned by the API against what you expect, rather than trusting the code alone.
- Fund-master codes: 40
- Nav-history codes: 40
- Coverage: 100.0% of master codes have NAV history
- All fund-master codes have matching NAV history.