# Mutual Fund Analytics Project

This project takes 10 mutual fund datasets (NAV history, investor
transactions, performance, AUM, portfolio holdings, benchmark indices,
and a few industry-wide reference files), cleans them up, and loads the
core ones into a SQLite database I can run SQL queries against.

## What's in this folder

- **data/raw** — the original 10 CSV files, untouched
- **data/processed** — cleaned versions of all 10 files
- **notebooks** — Jupyter notebooks for charting the data
- **sql** — extra SQL scripts
- **dashboard** — dashboard stuff (coming later)
- **reports** — summary notes about the data
- **data_ingestion.py** — Day 1: loads and profiles the raw CSVs, checks for problems
- **live_nav_fetch.py** — Day 1: pulls live NAV data from a free API
- **data_cleaning.py** — Day 2: cleans all 10 CSVs (dates, duplicates, bad values, etc.)
- **schema.sql** — Day 2: defines the database tables (the "star schema")
- **load_to_sqlite.py** — Day 2: builds `bluestock_mf.db` and loads the cleaned data into it
- **queries.sql** — Day 2: 13 SQL queries that answer real questions about the data
- **data_dictionary.md** — Day 2: full documentation of every table and column in the database
- **bluestock_mf.db** — the actual database file (generated, not hand-written)
- **requirements.txt** — Python packages this project needs

## How to set it up

1. Make a virtual environment:
   ```cmd
   python -m venv venv
   venv\Scripts\activate
   ```
2. Install the packages:
   ```cmd
   pip install -r requirements.txt
   ```

## How to run it, in order

1. Put the 10 CSV files into `data/raw`.
2. (Optional) Pull live NAV data:
   ```cmd
   python live_nav_fetch.py
   ```
3. Check the raw data for problems:
   ```cmd
   python data_ingestion.py
   ```
4. Clean all the data:
   ```cmd
   python data_cleaning.py
   ```
5. Build the database from the cleaned data:
   ```cmd
   python load_to_sqlite.py
   ```
   This creates `bluestock_mf.db` right in this folder.
6. Look at the data — either:
   - Open `bluestock_mf.db` in **DB Browser for SQLite** and click around, or
   - Run the queries in `queries.sql` from there, or
   - Read from it in Python/a notebook with `sqlite3` + `pandas.read_sql_query()`.

## Where to look things up

If I (or anyone else) forget what a column means or which file it came
from, **`data_dictionary.md` has the full answer** — every table, every
column, what cleaning rule was applied, and which of the 10 raw files
feeds it. I don't repeat all of that here on purpose, so there's only one
place to keep updated.

## Things I learned / got stuck on

- VS Code's notebook kernel can silently be a *different* Python than my
  venv (e.g. Anaconda) — always check `sys.executable` in a cell if
  something "already installed" still says missing.
- After installing a new package, restart the kernel — re-running the
  cell isn't enough.
- Real CSV column names almost never match my first guess (e.g.
  `amount_inr` instead of `amount`) — I had to adjust the cleaning script
  to look for the actual names in my files.
- Matching column names by a loose substring (like "3y") is risky if two
  different columns both contain it (`return_3yr_pct` vs
  `benchmark_3yr_pct`) — got a duplicate-column error from exactly this.
- `pandas.to_datetime` can silently misread `DD-MM-YYYY` dates if you
  don't tell it which part is the day — I fixed this in `data_cleaning.py`
  by parsing ISO dates first and only falling back for anything that
  didn't parse.
- Not every raw file fits neatly into the database — 4 of my 10 files are
  industry-wide aggregates with no fund code to join on, so they're
  cleaned but not loaded into `bluestock_mf.db` yet (documented in
  `data_dictionary.md`).

## Next steps

- Maybe add the 4 leftover files (AUM by fund house, SIP inflows,
  category inflows, folio counts) into the database as their own table
  - Build a dashboard on top of the queries
  - Add more charts in the notebook
