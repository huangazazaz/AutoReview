from autotrade.indicators.atr import ATR
import pandas as pd
atr = ATR(period=14)
df = pd.DataFrame({
    "high": [10, 11, 12, 11, 10, 11, 12, 13, 14, 13, 12, 11, 10, 11, 12],
    "low":  [8,   9,  9,  8,  7,  8,  9, 10, 11, 10,  9,  8,  7,  8,  9],
    "close":[9,  10, 11, 10,  9, 10, 11, 12, 13, 12, 11, 10,  9, 10, 11],
}, dtype=float)
result = atr.compute(df)
vals = result["ind_atr_14"]
print("Values:", vals.tolist())
print("row13 nan?", pd.isna(vals.iloc[13]))
print("first13 all nan?", vals.iloc[:13].isna().all())
