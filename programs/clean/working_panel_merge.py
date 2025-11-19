import pandas as pd
import numpy as np

deposit_interest_rate = pd.read_csv("data/processed/deposit_interest_rate.csv")
bank_credit = pd.read_csv("data/processed/bank_credit.csv")
instruments = pd.read_csv("data/processed/instruments.csv")

df = deposit_interest_rate.merge(bank_credit, on=['rssd9001', 'rssd9999', 'rssd9050'], how='left')
instruments = instruments[['RSSDID', 'sophistication_index_z', 'hhi_z', 'branch_density_z', 'NE', 'MA', 'EC', 'WC', 'SA', 'ES', 'WS', 'MT', 'PC']]
instruments.rename(columns={'RSSDID': 'rssd9001'}, inplace=True)
df = df.merge(instruments, on=['rssd9001'], how='left')

df.rename(columns={'rssd9001': 'Bank ID', 'rssd9999': 'Date'}, inplace=True)
df.drop(columns=['rssd9050', 'rssdfininstfilingtype'], inplace=True)

mask = ~df['interest_rate_on_deposit'].isna() & ~df['interest_rate_on_interest_bearing_deposit'].isna()
df = df[mask]
df = df.copy()

df['d_multifamily_loans'] = df['d_multifamily_loans'].fillna(0)
df['d_single_family_loans'] = df['d_single_family_loans'].fillna(0)
df['d_total_loans'] = df['d_total_loans'].fillna(0)
df['d_total_loans_not_for_sale'] = df['d_total_loans_not_for_sale'].fillna(0)
df['d_C&I'] = df['d_C&I'].fillna(0)

# small business lending flag (semi-annual) → carry forward last available within bank
df.sort_values(['Bank ID', 'Date'], inplace=True)
last_flag = df.groupby('Bank ID')['small_buz_lending_flag'].ffill()
df['small_buz_lending_flag_asof'] = np.where(last_flag.fillna(0) == 1, 1, 0)
df.drop(columns=['small_buz_lending_flag'], inplace=True)

mask = ~df['sophistication_index_z'].isna()
df = df[mask]
print(len(df))

# drop outliers in rate series using 0.5% / 99.5% thresholds
low_dep = df['interest_rate_on_deposit'].quantile(0.005)
high_dep = df['interest_rate_on_deposit'].quantile(0.995)
low_ib = df['interest_rate_on_interest_bearing_deposit'].quantile(0.005)
high_ib = df['interest_rate_on_interest_bearing_deposit'].quantile(0.995)
mask_rates = (
    (df['interest_rate_on_deposit'] >= low_dep) & (df['interest_rate_on_deposit'] <= high_dep) &
    (df['interest_rate_on_interest_bearing_deposit'] >= low_ib) & (df['interest_rate_on_interest_bearing_deposit'] <= high_ib)
)
df = df[mask_rates].copy()
print(len(df))

# keep z-scores strictly within [-10, 10]
mask_z = (
    df['sophistication_index_z'].between(-10, 10) &
    df['hhi_z'].between(-10, 10) &
    df['branch_density_z'].between(-10, 10)
)
df = df[mask_z].copy()
print(len(df))

ffr = pd.read_csv("data/processed/ffr_quarterly.csv")
df = df.merge(ffr, on=['Date'], how='left')

mask = (df['Date'] >= '2022-01-01') & (df['Date'] <= '2023-09-30')
df = df[mask]
print(len(df))

df.to_csv("data/working/working_panel.csv", index=False)