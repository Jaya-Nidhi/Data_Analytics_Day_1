-- queries.sql
-- Day 2: 10 analytical queries against bluestock_mf.db
-- Run with: sqlite3 bluestock_mf.db < queries.sql
-- or paste individual queries into a SQLite client / pandas read_sql_query().

-- 1. Top 5 funds by AUM (most recent snapshot per fund)
SELECT f.scheme_name, f.fund_house, a.aum_cr, d.full_date
FROM fact_aum a
JOIN dim_fund f ON f.amfi_code = a.amfi_code
JOIN dim_date d ON d.date_id = a.date_id
WHERE a.date_id = (
    SELECT MAX(date_id) FROM fact_aum a2 WHERE a2.amfi_code = a.amfi_code
)
ORDER BY a.aum_cr DESC
LIMIT 5;

-- 2. Average NAV per month, per fund
SELECT f.scheme_name, d.year, d.month, ROUND(AVG(n.nav), 2) AS avg_nav
FROM fact_nav n
JOIN dim_fund f ON f.amfi_code = n.amfi_code
JOIN dim_date d ON d.date_id = n.date_id
GROUP BY f.scheme_name, d.year, d.month
ORDER BY f.scheme_name, d.year, d.month;

-- 3. SIP year-over-year growth (total SIP amount per year + % change vs prior year)
WITH sip_by_year AS (
    SELECT d.year, SUM(t.amount) AS total_sip
    FROM fact_transactions t
    JOIN dim_date d ON d.date_id = t.date_id
    WHERE t.transaction_type = 'SIP'
    GROUP BY d.year
)
SELECT
    year,
    total_sip,
    ROUND(
        100.0 * (total_sip - LAG(total_sip) OVER (ORDER BY year))
        / LAG(total_sip) OVER (ORDER BY year),
        2
    ) AS yoy_growth_pct
FROM sip_by_year
ORDER BY year;

-- 4. Transactions by state
SELECT state, COUNT(*) AS num_transactions, SUM(amount) AS total_amount
FROM fact_transactions
GROUP BY state
ORDER BY total_amount DESC;

-- 5. Funds with expense_ratio < 1%
SELECT f.scheme_name, f.fund_house, p.expense_ratio
FROM fact_performance p
JOIN dim_fund f ON f.amfi_code = p.amfi_code
WHERE p.expense_ratio < 1.0
ORDER BY p.expense_ratio ASC;

-- 6. Total AUM by fund house (most recent snapshot per fund, summed)
SELECT f.fund_house, SUM(a.aum_cr) AS total_aum_cr
FROM fact_aum a
JOIN dim_fund f ON f.amfi_code = a.amfi_code
WHERE a.date_id = (
    SELECT MAX(date_id) FROM fact_aum a2 WHERE a2.amfi_code = a.amfi_code
)
GROUP BY f.fund_house
ORDER BY total_aum_cr DESC;

-- 7. Top 5 funds by 1-year return
SELECT f.scheme_name, f.fund_house, p.return_1y
FROM fact_performance p
JOIN dim_fund f ON f.amfi_code = p.amfi_code
ORDER BY p.return_1y DESC
LIMIT 5;

-- 8. KYC status breakdown of transactions
SELECT kyc_status, COUNT(*) AS num_transactions, SUM(amount) AS total_amount
FROM fact_transactions
GROUP BY kyc_status
ORDER BY num_transactions DESC;

-- 9. Monthly transaction volume and amount trend
SELECT d.year, d.month, COUNT(*) AS num_transactions, SUM(t.amount) AS total_amount
FROM fact_transactions t
JOIN dim_date d ON d.date_id = t.date_id
GROUP BY d.year, d.month
ORDER BY d.year, d.month;

-- 10. Funds in the master list with zero recorded transactions
SELECT f.scheme_name, f.fund_house
FROM dim_fund f
LEFT JOIN fact_transactions t ON t.amfi_code = f.amfi_code
WHERE t.transaction_id IS NULL;
