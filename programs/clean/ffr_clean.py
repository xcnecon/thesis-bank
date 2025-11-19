import pandas as pd
import numpy as np

df = pd.read_csv("data/raw/ffr_upper_limit.csv")

df.rename(columns={'date': 'Date'}, inplace=True)

df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
df = df.dropna(subset=['Date']).copy()
df.sort_values('Date', inplace=True)

# Resample to quarter-end using the last available daily value in the quarter
q = (
    df.set_index('Date')
      .resample('Q')
      .last()
      .reset_index()
)

# Quarter-over-quarter change in the FFR upper limit (level differences, in p.p.)
q['d_ffr'] = q['ffr_upper'].diff()

# Keep only quarters from 2022Q1 to 2024Q2 (inclusive)
q = q[(q['Date'] >= pd.Timestamp('2022-01-01')) & (q['Date'] <= pd.Timestamp('2024-06-30'))].copy()

# Cumulative change since 2022Q1
base = q['ffr_upper'].iloc[0] if len(q) else np.nan
q['cum_d_ffr'] = q['ffr_upper'] - base + 0.25

q.to_csv("data/processed/ffr_quarterly.csv", index=False)
