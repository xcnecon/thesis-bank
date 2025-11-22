import pandas as pd
import numpy as np

rcon1 = pd.read_csv("data/raw/rcon_control_1.csv", parse_dates=["rssd9999"])
# De-dupe by keys, keeping the latest submission by date
rcon1['rssdsubmissiondate'] = pd.to_datetime(rcon1['rssdsubmissiondate'], errors='coerce')
rcon1.sort_values(['rssd9001', 'rssd9999', 'rssdsubmissiondate'], inplace=True)
rcon1 = rcon1.drop_duplicates(subset=['rssd9001', 'rssd9999'], keep='last')
rcon1.drop(columns=['rssdsubmissiondate'], inplace=True)

rcon2 = pd.read_csv("data/raw/rcon_control_2.csv", parse_dates=["rssd9999"])
rcon2['rssdsubmissiondate'] = pd.to_datetime(rcon2['rssdsubmissiondate'], errors='coerce')
rcon2.sort_values(['rssd9001', 'rssd9999', 'rssdsubmissiondate'], inplace=True)
rcon2 = rcon2.drop_duplicates(subset=['rssd9001', 'rssd9999'], keep='last')
rcon2.drop(columns=['rssdsubmissiondate'], inplace=True)

riad = pd.read_csv("data/raw/riad_control.csv", parse_dates=["rssd9999"])
riad['rssdsubmissiondate'] = pd.to_datetime(riad['rssdsubmissiondate'], errors='coerce')
riad.sort_values(['rssd9001', 'rssd9999', 'rssdsubmissiondate'], inplace=True)
riad = riad.drop_duplicates(subset=['rssd9001', 'rssd9999'], keep='last')
riad.drop(columns=['rssdsubmissiondate'], inplace=True)

df = rcon1.merge(rcon2, on=["rssd9001", "rssd9999"], how="left")
df = df.merge(riad, on=["rssd9001", "rssd9999"], how="left")

df['ROA'] = df['riad4340'] / df['rcon2170']
df['core_deposit_share'] = (df['rcon2210'] + df['rcon0352'] + df['rcon6810'] + df['rconj473'] + df['rcon6648']) / df['rcon2170']
df['wholesale_share'] = (df['rcon3353'] + df['rcon3200'] + df['rconj474'] + df['rcon3190']) / df['rcon2170']
df['asset_to_equity'] = df['rcon2170'] / df['rcon3210']
df['log_asset'] = np.log(df['rcon2170'])

df = df[['rssd9001', 'rssd9999', 'ROA', 'core_deposit_share', 'wholesale_share', 'asset_to_equity', 'log_asset']]

df.to_csv("data/processed/controls.csv", index=False)