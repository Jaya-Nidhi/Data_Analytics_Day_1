import sqlite3
import pandas as pd

conn = sqlite3.connect("bluestock_mf.db")
df = pd.read_sql_query("SELECT * FROM dim_fund", conn)
print(df)
conn.close()