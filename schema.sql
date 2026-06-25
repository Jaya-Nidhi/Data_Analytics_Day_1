-- schema.sql
-- Day 2: Star schema for the Mutual Fund Analytics SQLite database.
--
-- dim_fund and dim_date are the dimension tables.
-- fact_nav, fact_transactions, fact_performance, fact_aum are the fact tables,
-- each linked to dim_fund and dim_date by foreign key.

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS fact_aum;
DROP TABLE IF EXISTS fact_performance;
DROP TABLE IF EXISTS fact_transactions;
DROP TABLE IF EXISTS fact_nav;
DROP TABLE IF EXISTS dim_fund;
DROP TABLE IF EXISTS dim_date;

-- ---------------------------------------------------------------------
-- Dimension: one row per mutual fund scheme
-- ---------------------------------------------------------------------
CREATE TABLE dim_fund (
    amfi_code     INTEGER PRIMARY KEY,
    fund_house    TEXT,
    scheme_name   TEXT,
    category      TEXT,
    sub_category  TEXT,
    risk_grade    TEXT
);

-- ---------------------------------------------------------------------
-- Dimension: one row per calendar date that appears anywhere in the facts
-- date_id is YYYYMMDD as an integer, e.g. 20240115, for fast joins/sorts
-- ---------------------------------------------------------------------
CREATE TABLE dim_date (
    date_id       INTEGER PRIMARY KEY,
    full_date     TEXT NOT NULL,      -- ISO format 'YYYY-MM-DD'
    year          INTEGER NOT NULL,
    quarter       INTEGER NOT NULL,
    month         INTEGER NOT NULL,
    month_name    TEXT NOT NULL,
    day           INTEGER NOT NULL,
    day_of_week   TEXT NOT NULL,
    is_weekend    INTEGER NOT NULL    -- 0 = weekday, 1 = weekend
);

-- ---------------------------------------------------------------------
-- Fact: daily NAV per fund
-- ---------------------------------------------------------------------
CREATE TABLE fact_nav (
    nav_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    amfi_code     INTEGER NOT NULL,
    date_id       INTEGER NOT NULL,
    nav           REAL NOT NULL,
    FOREIGN KEY (amfi_code) REFERENCES dim_fund(amfi_code),
    FOREIGN KEY (date_id)   REFERENCES dim_date(date_id)
);

-- ---------------------------------------------------------------------
-- Fact: investor transactions (SIP / Lumpsum / Redemption)
-- ---------------------------------------------------------------------
CREATE TABLE fact_transactions (
    transaction_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    amfi_code         INTEGER NOT NULL,
    date_id           INTEGER NOT NULL,
    investor_id       TEXT,
    transaction_type  TEXT NOT NULL,   -- SIP / Lumpsum / Redemption
    amount            REAL NOT NULL,
    kyc_status        TEXT,
    state             TEXT,
    city              TEXT,
    city_tier         TEXT,
    age_group         TEXT,
    gender            TEXT,
    annual_income_lakh REAL,
    payment_mode      TEXT,
    FOREIGN KEY (amfi_code) REFERENCES dim_fund(amfi_code),
    FOREIGN KEY (date_id)   REFERENCES dim_date(date_id)
);

-- ---------------------------------------------------------------------
-- Fact: scheme performance / returns snapshot
-- ---------------------------------------------------------------------
CREATE TABLE fact_performance (
    performance_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    amfi_code       INTEGER NOT NULL,
    date_id         INTEGER NOT NULL,
    return_1y       REAL,
    return_3y       REAL,
    return_5y       REAL,
    expense_ratio   REAL,
    alpha             REAL,
    beta              REAL,
    sharpe_ratio      REAL,
    sortino_ratio     REAL,
    std_dev_ann_pct   REAL,
    max_drawdown_pct  REAL,
    benchmark_3yr_pct REAL,
    morningstar_rating INTEGER,
    FOREIGN KEY (amfi_code) REFERENCES dim_fund(amfi_code),
    FOREIGN KEY (date_id)   REFERENCES dim_date(date_id)
);

-- ---------------------------------------------------------------------
-- Fact: assets under management snapshot
-- ---------------------------------------------------------------------
CREATE TABLE fact_aum (
    aum_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    amfi_code     INTEGER NOT NULL,
    date_id       INTEGER NOT NULL,
    aum_cr        REAL NOT NULL,       -- AUM in INR crore
    FOREIGN KEY (amfi_code) REFERENCES dim_fund(amfi_code),
    FOREIGN KEY (date_id)   REFERENCES dim_date(date_id)
);

-- ---------------------------------------------------------------------
-- Indexes to speed up the common fund+date join pattern
-- ---------------------------------------------------------------------
CREATE INDEX idx_fact_nav_fund_date  ON fact_nav(amfi_code, date_id);
CREATE INDEX idx_fact_txn_fund_date  ON fact_transactions(amfi_code, date_id);
CREATE INDEX idx_fact_perf_fund_date ON fact_performance(amfi_code, date_id);
CREATE INDEX idx_fact_aum_fund_date  ON fact_aum(amfi_code, date_id);