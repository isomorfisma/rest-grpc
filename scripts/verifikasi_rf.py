#!/usr/bin/env python3
"""Verifikasi Random Forest manual terhadap scikit-learn dengan pengaturan yang sama.

scikit-learn hanya dipakai di sini sebagai pembanding, tidak untuk membangun model analisis.
Contoh: python3 scripts/verifikasi_rf.py   (butuh: pip install scikit-learn)
"""
import os
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfg
import rf_manual as rfm

c = cfg.load()
SUF = cfg.suffix(c)
DATA = c["output"]["data_dir"]
MAKS_FITUR = 2                                  # sama dengan RF_MAKS_FITUR di analyze.py

df = pd.read_csv(f"{DATA}/dataset{SUF}.csv")
X = df[["protocol_code", "payload_bytes", "concurrency"]].to_numpy(float)
y, grup = np.log(df.p50_ms.to_numpy()), df.combo_id.to_numpy()

model = {
    "manual": lambda: rfm.RandomForestManual(300, 6, 3, MAKS_FITUR, seed=42),
    "scikit-learn": lambda: RandomForestRegressor(n_estimators=300, max_depth=6, min_samples_leaf=3,
                                                  max_features=MAKS_FITUR, random_state=42),
}
pred, baris = {}, []
for nama, buat in model.items():
    p = np.full(len(y), np.nan)
    for latih, uji in rfm.leave_one_group_out(grup):
        p[uji] = buat().fit(X[latih], y[latih]).predict(X[uji])
    pred[nama] = p
    imp = buat().fit(X, y).feature_importances_
    baris.append({"implementasi": nama, "R2_log": rfm.r2(y, p), "RMSE_ms": rfm.rmse(np.exp(y), np.exp(p)),
                  "MAPE": rfm.mape(np.exp(y), np.exp(p)), "imp_protokol": imp[0], "imp_payload": imp[1],
                  "imp_concurrency": imp[2]})
hasil = pd.DataFrame(baris).round(3)
hasil.to_csv(f"{DATA}/tabel_verifikasi_rf{SUF}.csv", index=False)
print(hasil.to_string(index=False))
beda = np.abs(np.exp(pred["manual"]) / np.exp(pred["scikit-learn"]) - 1)
print(f"Korelasi prediksi (log): {np.corrcoef(pred['manual'], pred['scikit-learn'])[0, 1]:.4f}; "
      f"selisih prediksi median {np.median(beda):.1%}, maksimum {beda.max():.1%}")
