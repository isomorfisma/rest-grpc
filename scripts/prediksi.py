#!/usr/bin/env python3
"""Estimasi p50 REST dan gRPC dengan model Random Forest manual hasil analyze.py.

Contoh: python3 scripts/prediksi.py --payload 200000 --concurrency 300
Model hanya berlaku di dalam rentang uji (Random Forest tidak dapat mengekstrapolasi).
"""
import argparse
import os
import pickle
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rf_manual  # noqa: F401  (dibutuhkan pickle untuk memuat kelas model)

ap = argparse.ArgumentParser()
ap.add_argument("--payload", type=float, required=True, help="ukuran payload JSON dalam byte")
ap.add_argument("--concurrency", type=float, required=True, help="jumlah virtual user")
ap.add_argument("--model", default="data/model_rf.pkl")
a = ap.parse_args()

m = pickle.load(open(a.model, "rb"))
(b0, b1), (c0, c1) = m["rentang_byte"], m["rentang_conc"]
if not (b0 <= a.payload <= b1 and c0 <= a.concurrency <= c1):
    sys.exit(f"Di luar rentang uji: payload {b0:.0f}–{b1:.0f} byte, concurrency {c0:.0f}–{c1:.0f}.")

est = {p: float(np.exp(m["model"].predict([[i, a.payload, a.concurrency]])[0]))
       for i, p in enumerate(m["protokol"])}
for p, v in est.items():
    print(f"{p.upper():5s} p50 ≈ {v:8.1f} ms")
(pa, va), (pb, vb) = est.items()
selisih = abs(va - vb) / max(va, vb)
if selisih < 0.05:
    print(f"Rekomendasi: setara (selisih {selisih:.0%} < 5%), pilih berdasarkan pertimbangan lain")
else:
    print(f"Rekomendasi: {(pa if va < vb else pb).upper()} (selisih {selisih:.0%})")
