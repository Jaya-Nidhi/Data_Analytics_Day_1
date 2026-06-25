# import pandas as pd
# print(pd.read_csv("data/raw/07_scheme_performance.csv").columns.tolist())

import pandas as pd
df = pd.read_csv("data/raw/08_investor_transactions.csv")
df['amount_inr'] = pd.to_numeric(df['amount_inr'], errors='coerce')
print(df.groupby('transaction_type')['amount_inr'].agg(['count', 'min', 'max']))
