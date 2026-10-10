#!/usr/bin/env python3
"""Analisis hasil eksperimen REST vs gRPC.

Lima bagian, dijalankan berurutan karena saling bergantung:
  1. Deskriptif dan heatmap        → Tabel 4.7, Gambar 4.2, Gambar 4.4
  2. ANOVA dan uji asumsi          → Tabel 4.8, Gambar 4.3
  3. Pemenang per sel + crossover  → Tabel 4.9, Tabel 4.10, Gambar 4.5
  4. Metrik pada beban tertinggi   → Tabel 4.11, Gambar 4.6, Tabel 4.14 (ekor), Tabel 4.15 (generator)
  5. Random Forest                 → Tabel 4.12, Tabel 4.13, Gambar 4.7, Gambar 4.8

Menjalankan sebagian: python3 scripts/analyze.py 4 5   (bagian 5 membutuhkan bagian 2)
Data pilot          : OVERRIDE=config/pilot.json python3 scripts/analyze.py
"""
import os
import sys

import matplotlib
import matplotlib.ticker
import numpy as np
import pandas as pd

matplotlib.use("Agg")                       # harus sebelum import pyplot
import matplotlib.pyplot as plt
import statsmodels.api as sm
from scipy import stats
from scipy.stats import ttest_ind
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_percentage_error, mean_squared_error, r2_score
from sklearn.model_selection import LeaveOneGroupOut
from statsmodels.formula.api import ols
from statsmodels.stats.multitest import multipletests

sys.path.insert(0, "scripts")
import cfg

# ---------------------------------------------------------------- setup bersama
c = cfg.load()
SUF = cfg.suffix(c)                           # "" untuk eksperimen penuh, "_pilot" untuk pilot
DATA, FIG = c["output"]["data_dir"], c["output"]["figures_dir"]
os.makedirs(FIG, exist_ok=True)
KELAS, CONC, PROTO = cfg.classes(c), c["concurrency_levels"], cfg.protocols(c)
BAGIAN = set(sys.argv[1:]) or {"1", "2", "3", "4", "5"}
GAYA = ["o-", "s--", "^:", "d-."]           # pembeda garis antar protokol
LABEL = {"rest": "REST", "grpc": "gRPC"}    # penulisan nama protokol pada gambar
nama = lambda p: LABEL.get(p, p.upper())

df = pd.read_csv(f"{DATA}/dataset{SUF}.csv")
df["log_p50"] = np.log(df.p50_ms)
print(f"{len(df)} run · {df.combo_id.nunique()} sel · bagian dijalankan: {sorted(BAGIAN)}\n")


def simpan(fig, nama):
    path = f"{FIG}/{nama}{SUF}.png"
    fig.savefig(path, dpi=200)
    plt.close(fig)                          # jangan biarkan figure menumpuk di RAM
    print("  gambar →", path)


def tabel(obj, nama, index=True):
    path = f"{DATA}/{nama}{SUF}.csv"
    obj.to_csv(path, index=index)
    print("  tabel  →", path)


# ============================ 1. Deskriptif dan heatmap =======================
if "1" in BAGIAN:
    print("[1] Deskriptif dan heatmap")
    metrik = ["p50_ms", "p95_ms", "p99_ms", "throughput_rps", "cpu_percent", "error_rate"]
    tabel(df.groupby(["protocol", "payload_class", "concurrency"])[metrik].agg(["mean", "std"]).round(2),
          "tabel_4_7_deskriptif")

    # Gambar 4.2 — satu panel per protokol (jumlah panel mengikuti konfigurasi)
    med = df.groupby(["protocol", "payload_class", "concurrency"]).p50_ms.median()
    fig, axes = plt.subplots(1, len(PROTO), figsize=(5 * len(PROTO), 4),
                             constrained_layout=True, squeeze=False)
    for ax, p in zip(axes[0], PROTO):
        grid = med[p].unstack().loc[KELAS, CONC]
        im = ax.imshow(np.log10(grid.values), cmap="viridis")
        ax.set_title(nama(p))
        ax.set_xticks(range(len(CONC)), CONC)
        ax.set_yticks(range(len(KELAS)), KELAS)
        ax.set_xlabel("Concurrency (VU)")
        ax.set_ylabel("Kelas payload")
        for i in range(len(KELAS)):
            for k in range(len(CONC)):
                ax.text(k, i, f"{grid.values[i, k]:.0f}", ha="center", va="center", color="w", fontsize=8)
    fig.colorbar(im, ax=axes[0], label="log10 median p50 (ms)")
    simpan(fig, "gambar_4_2_heatmap_p50")

    # Gambar 4.4 — rasio antar dua protokol (hanya bila protokolnya tepat dua)
    if len(PROTO) == 2:
        A, B = PROTO
        rasio = (med[A] / med[B]).unstack().loc[KELAS, CONC]
        lim = np.abs(np.log2(rasio.values)).max()
        fig, ax = plt.subplots(figsize=(1.2 * len(CONC) + 3, 0.7 * len(KELAS) + 1.6),
                               constrained_layout=True)
        im = ax.imshow(np.log2(rasio.values), cmap="RdBu", vmin=-lim, vmax=lim)
        ax.set_xticks(range(len(CONC)), CONC)
        ax.set_yticks(range(len(KELAS)), KELAS)
        ax.set_xlabel("Concurrency (VU)")
        ax.set_ylabel("Kelas payload")
        for i in range(len(KELAS)):
            for k in range(len(CONC)):
                ax.text(k, i, f"{rasio.values[i, k]:.2f}×", ha="center", va="center", fontsize=9)
        fig.colorbar(im, label=f"log2({nama(A)} / {nama(B)}) · biru = {nama(B)} lebih cepat")
        simpan(fig, "gambar_4_4_rasio")

# ============================ 2. ANOVA dan uji asumsi =========================
if "2" in BAGIAN:
    print("\n[2] ANOVA tiga faktor")
    formula = "log_p50 ~ C(protocol) * C(payload_class) * C(concurrency)"
    if df.block.notna().any() and df.block.nunique() > 1:
        formula += " + C(block)"            # blok hanya masuk model bila lebih dari satu putaran
    print("  model:", formula)

    model = ols(formula, data=df).fit()
    aov = sm.stats.anova_lm(model, typ=2)
    aov["eta2_partial"] = aov.sum_sq / (aov.sum_sq + aov.loc["Residual", "sum_sq"])   # Persamaan 2.2
    aov.loc["Residual", "eta2_partial"] = np.nan
    tabel(aov.round(4), "tabel_4_8_anova")
    print(aov.round(4))

    # Uji asumsi (untuk Lampiran)
    print("  Shapiro-Wilk:", stats.shapiro(model.resid))
    kelompok = [g.log_p50.values for _, g in df.groupby(["protocol", "payload_class", "concurrency"])]
    print("  Levene      :", stats.levene(*kelompok))
    fig, ax = plt.subplots(1, 2, figsize=(9, 3.5), constrained_layout=True)
    ax[0].scatter(model.fittedvalues, model.resid, s=6)
    ax[0].axhline(0, color="k", lw=.8)
    ax[0].set_xlabel("Nilai prediksi"); ax[0].set_ylabel("Residual")
    sm.qqplot(model.resid, line="s", ax=ax[1])
    simpan(fig, "lampiran_asumsi_anova")

    # Bila ragam tidak homogen, laporkan juga versi robust
    aov_hc3 = sm.stats.anova_lm(model, typ=2, robust="hc3")
    tabel(aov_hc3.round(4), "tabel_4_8_anova_hc3")

    # Gambar 4.3 — interaction plot, satu garis per protokol
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), constrained_layout=True)
    for p, mk in zip(PROTO, GAYA):
        sub = df[df.protocol == p]
        axes[0].plot(KELAS, sub.groupby("payload_class").log_p50.mean().loc[KELAS], mk, label=nama(p))
        axes[1].plot([str(x) for x in CONC], sub.groupby("concurrency").log_p50.mean().loc[CONC],
                     mk, label=nama(p))
    axes[0].set_xlabel("Kelas payload")
    axes[1].set_xlabel("Concurrency (VU)")
    for a in axes:
        a.set_ylabel("Rata-rata log(p50)")
        a.legend()
    simpan(fig, "gambar_4_3_interaksi")

# =================== 3. Pemenang per sel dan lokasi crossover ==================
if "3" in BAGIAN and len(PROTO) == 2:
    print("\n[3] Pemenang per sel dan crossover")
    A, B = PROTO

    # Tabel 4.9 — uji beda di setiap sel, dengan koreksi Holm dan ambang praktis 5%
    baris = []
    for (s, cc), g in df.groupby(["payload_class", "concurrency"]):
        a, b = g[g.protocol == A].log_p50, g[g.protocol == B].log_p50
        selisih = np.exp(a.mean() - b.mean()) - 1      # +0,20 → A 20% lebih lambat
        baris.append((s, cc, selisih, ttest_ind(a, b, equal_var=False).pvalue))
    sel = pd.DataFrame(baris, columns=["payload_class", "concurrency", "selisih", "p"])
    sel["p_holm"] = multipletests(sel.p, method="holm")[1]
    sel["pemenang"] = np.select(
        [(sel.p_holm < .05) & (sel.selisih > .05), (sel.p_holm < .05) & (sel.selisih < -.05)],
        [B, A], default="setara")
    tabel(sel, "tabel_4_9_pemenang", index=False)
    print(sel.to_string(index=False))

    # Tabel 4.10 — lokasi crossover dari rasio p50 berpasangan.
    # Regresi logistik (rencana awal) tidak dapat difit bila hasil terpisah sempurna: setiap pasangan
    # di bawah suatu ukuran dimenangkan A dan di atasnya dimenangkan B, sehingga koefisiennya tak hingga.
    # Model regresi kontinu pada rasio juga tidak dipakai karena bentuk fungsinya sendiri yang
    # menentukan titik potong. Yang dilaporkan: (1) rentang yang pasti dari data, yaitu dua kelas
    # bertetangga tempat pemenang berganti, dan (2) estimasi titik crossover dengan interpolasi
    # linear log-rasio terhadap log ukuran payload di antara kedua kelas, beserta interval
    # kepercayaan 95% dari bootstrap repetisi.
    pasang = df.pivot_table(index=["payload_class", "payload_bytes", "concurrency", "rep"],
                            columns="protocol", values="p50_ms").reset_index()
    pasang["log_rasio"] = np.log(pasang[A] / pasang[B])         # > 0 → B lebih cepat
    pasang["menang_b"] = (pasang.log_rasio > 0).astype(int)
    rng = np.random.default_rng(c["experiment"]["seed"])

    def potong(lb1, y1, lb2, y2):                               # titik y = 0 pada sumbu log10(byte)
        return lb1 + (0 - y1) / (y2 - y1) * (lb2 - lb1)

    hasil, kurva = [], []
    for cc, g in pasang.groupby("concurrency"):
        sel_c = g.groupby("payload_bytes").log_rasio
        rata = sel_c.mean().sort_index()
        sampel = {b: v.values for b, v in sel_c}
        for b, m in rata.items():
            ci = np.percentile([rng.choice(sampel[b], len(sampel[b])).mean() for _ in range(2000)], [2.5, 97.5])
            kurva.append((cc, b, m, *ci, g[g.payload_bytes == b].menang_b.mean()))
        bs = rata.index.values
        for b1, b2 in zip(bs[:-1], bs[1:]):
            if np.sign(rata[b1]) == np.sign(rata[b2]):
                continue
            lb1, lb2 = np.log10(b1), np.log10(b2)
            titik = potong(lb1, rata[b1], lb2, rata[b2])
            boot = [potong(lb1, rng.choice(sampel[b1], len(sampel[b1])).mean(),
                           lb2, rng.choice(sampel[b2], len(sampel[b2])).mean()) for _ in range(2000)]
            lo, hi = np.percentile(boot, [2.5, 97.5])
            hasil.append({"concurrency": cc, "kelas_bawah_byte": int(b1), "kelas_atas_byte": int(b2),
                          "pemenang_bawah": A if rata[b1] < 0 else B, "pemenang_atas": A if rata[b2] < 0 else B,
                          "crossover_kb": round(10 ** titik / 1000, 1),
                          "ci95_bawah_kb": round(10 ** lo / 1000, 1), "ci95_atas_kb": round(10 ** hi / 1000, 1)})
    silang = pd.DataFrame(hasil)
    if silang.empty:
        print("  Tidak ada perubahan pemenang di rentang uji: tidak ada crossover.")
    else:
        tabel(silang, "tabel_4_10_crossover", index=False)
        print(silang.to_string(index=False))
    # Regresi logistik sesuai persamaan (2.3)–(2.4). Bila data terpisah sempurna, estimasi
    # maximum likelihood tidak ada (koefisien membesar tanpa batas) dan interpolasi di atas dipakai.
    pasang["lp"] = np.log10(pasang.payload_bytes)
    pasang["lc"] = np.log10(pasang.concurrency)
    import warnings
    import statsmodels.formula.api as smf
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error")                      # peringatan separasi diperlakukan sebagai gagal
            logit = smf.logit("menang_b ~ lp * lc", data=pasang).fit(disp=False, maxiter=200)
        if not logit.mle_retvals.get("converged", False) or np.abs(logit.params).max() > 100:
            raise ValueError("tidak konvergen / koefisien tak terbatas")
        with open(f"{DATA}/tabel_4_10_logit{SUF}.txt", "w") as f:
            f.write(str(logit.summary()))
        b0, b1, b2, b3 = (logit.params[k] for k in ["Intercept", "lp", "lc", "lp:lc"])
        batas = pd.DataFrame([{"concurrency": cc,
                               "batas_logit_kb": round(10 ** (-(b0 + b2 * np.log10(cc)) / (b1 + b3 * np.log10(cc))) / 1000, 1)}
                              for cc in CONC])
        tabel(batas, "tabel_4_10b_batas_logit", index=False)
        print(logit.summary2().tables[1].round(3).to_string())
        print(batas.to_string(index=False))
    except Exception as e:
        print(f"  Regresi logistik tidak dapat difit ({type(e).__name__}): data terpisah sempurna, "
              "lokasi crossover memakai interpolasi pada Tabel 4.10.")

    # Gambar 4.5 — rasio p50 A/B terhadap ukuran payload, satu garis per level concurrency
    k = pd.DataFrame(kurva, columns=["concurrency", "payload_bytes", "m", "lo", "hi", "frac_b"])
    fig, ax = plt.subplots(figsize=(6.4, 4.2), constrained_layout=True)
    for (cc, g), mk in zip(k.groupby("concurrency"), GAYA):
        ax.errorbar(g.payload_bytes, np.exp(g.m), yerr=[np.exp(g.m) - np.exp(g.lo), np.exp(g.hi) - np.exp(g.m)],
                    fmt=mk, capsize=3, label=f"{cc} VU")
    for _, r in silang.iterrows():
        ax.errorbar(r.crossover_kb * 1000, 1, xerr=[[r.crossover_kb * 1000 - r.ci95_bawah_kb * 1000],
                                                    [r.ci95_atas_kb * 1000 - r.crossover_kb * 1000]],
                    fmt="kx", capsize=4, ms=7)
    ax.axhline(1, color="k", lw=.8)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FormatStrFormatter("%.2g"))
    ax.yaxis.set_minor_formatter(matplotlib.ticker.FormatStrFormatter("%.2g"))
    ax.set_xlabel("Ukuran payload JSON (byte)")
    ax.set_ylabel(f"Rasio p50 {nama(A)} / {nama(B)}")
    ax.text(.02, .97, f"di atas 1: {nama(B)} lebih cepat", transform=ax.transAxes, va="top", fontsize=8)
    ax.text(.02, .03, f"di bawah 1: {nama(A)} lebih cepat", transform=ax.transAxes, va="bottom", fontsize=8)
    ax.legend(title="Concurrency")
    simpan(fig, "gambar_4_5_crossover")

# ================= 4. Metrik pada level concurrency tertinggi =================
if "4" in BAGIAN:
    cmax = max(CONC)                        # ikut konfigurasi, bukan angka tetap
    print(f"\n[4] Metrik pada concurrency {cmax} VU")
    top = df[df.concurrency == cmax]
    kol = ["cpu_percent", "p95_ms", "p99_ms", "error_rate", "throughput_rps"]
    tabel(top.groupby(["payload_class", "protocol"])[kol].mean().unstack("protocol").loc[KELAS].round(2),
          "tabel_4_11_concurrency_max")

    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), constrained_layout=True)
    for p, mk in zip(PROTO, GAYA):
        g = top[top.protocol == p].groupby("payload_class")
        axes[0].plot(KELAS, g.cpu_percent.mean().loc[KELAS], mk, label=nama(p))
        axes[1].plot(KELAS, g.p99_ms.mean().loc[KELAS], mk, label=nama(p))
    axes[0].set_ylabel("CPU (% satu core)")
    axes[1].set_ylabel("p99 (ms)"); axes[1].set_yscale("log")
    for a in axes:
        a.set_xlabel("Kelas payload"); a.legend()
    fig.suptitle(f"Concurrency {cmax} VU")
    simpan(fig, "gambar_4_6_concurrency_max")

    # Tabel 4.14 — ekor dan kestabilan per sel: rasio p99/p50 dan koefisien variasi p50 antar-repetisi
    ekor = df.groupby(["payload_class", "concurrency", "protocol"]).agg(
        p50_ms=("p50_ms", "median"), p95_ms=("p95_ms", "median"), p99_ms=("p99_ms", "median"),
        cv_p50=("p50_ms", lambda v: v.std() / v.mean()))
    ekor["p99_per_p50"] = ekor.p99_ms / ekor.p50_ms
    tabel(ekor.unstack("protocol").reindex(KELAS, level=0).round(3), "tabel_4_14_ekor_variabilitas")

    # Tabel 4.15 — beban pembangkit beban (k6): bukti generator bukan bottleneck
    if "gen_cpu_pct" in df:
        gen = df.groupby(["protocol", "payload_class", "concurrency"]).agg(
            gen_cpu_rata=("gen_cpu_pct", "mean"), gen_cpu_maks=("gen_cpu_pct", "max"),
            gen_rss_maks_mb=("gen_rss_mb", "max"), little_ratio=("little_ratio", "mean"))
        tabel(gen.unstack("protocol").reindex(KELAS, level=0).round(2), "tabel_4_15_generator")
        print(f"  CPU k6 maksimum: {df.gen_cpu_pct.max():.0f}% · little_ratio "
              f"{df.little_ratio.min():.2f}–{df.little_ratio.max():.2f}")

# ============================ 5. Random Forest ================================
if "5" in BAGIAN:
    print("\n[5] Random Forest dengan leave-one-group-out")
    FITUR = ["protocol_code", "payload_bytes", "concurrency"]
    X, y, grup = df[FITUR], df.log_p50, df.combo_id

    def rf():
        return RandomForestRegressor(n_estimators=300, max_depth=6, min_samples_leaf=3,
                                     random_state=42, n_jobs=1)      # n_jobs=1: hemat RAM

    pred = pd.Series(np.nan, index=df.index)
    for latih, uji in LeaveOneGroupOut().split(X, y, grup):           # satu sel ditahan per lipatan
        pred.iloc[uji] = rf().fit(X.iloc[latih], y.iloc[latih]).predict(X.iloc[uji])

    aktual_ms, pred_ms = np.exp(y), np.exp(pred)
    akurasi = pd.Series({
        "R2_log": round(r2_score(y, pred), 3),
        "RMSE_ms": round(mean_squared_error(aktual_ms, pred_ms) ** 0.5, 1),
        "MAPE": round(mean_absolute_percentage_error(aktual_ms, pred_ms), 3),
    })
    tabel(akurasi, "tabel_4_12_akurasi_rf")
    print(akurasi.to_string())

    # Gambar 4.7 — prediksi vs aktual
    fig, ax = plt.subplots(figsize=(4.8, 4.5), constrained_layout=True)
    for p in PROTO:
        m = (df.protocol == p).values
        ax.scatter(aktual_ms[m], pred_ms[m], s=12, alpha=.6, label=nama(p))
    lo, hi = aktual_ms.min(), aktual_ms.max()
    ax.plot([lo, hi], [lo, hi], "k--", lw=1)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("p50 aktual (ms)"); ax.set_ylabel("p50 prediksi LOGO (ms)")
    ax.legend()
    simpan(fig, "gambar_4_7_pred_vs_aktual")

    # Gambar 4.8 — feature importance dibanding eta-squared (butuh bagian 2)
    akhir = rf().fit(X, y)
    penting = pd.Series(akhir.feature_importances_, index=FITUR)
    if "aov" in globals():
        eta = aov.eta2_partial.reindex(["C(protocol)", "C(payload_class)", "C(concurrency)"]).values
        fig, ax = plt.subplots(figsize=(6, 3.2), constrained_layout=True)
        pos = np.arange(3)
        ax.bar(pos - .2, penting.values, .4, label="Feature importance RF")
        ax.bar(pos + .2, eta / eta.sum(), .4, label="η²p ANOVA (dinormalisasi)")
        ax.set_xticks(pos, ["Protokol", "Payload", "Concurrency"])
        ax.legend()
        simpan(fig, "gambar_4_8_importance")
    else:
        print("  Gambar 4.8 dilewati: jalankan bagian 2 lebih dulu (butuh tabel ANOVA).")
    print(penting.round(3).to_string())

    # Tabel 4.13 — estimasi pada titik tengah geometris antar level yang diuji.
    # Titik-titik ini otomatis menyesuaikan bila kelas atau level di konfigurasi berubah.
    b_uji = np.sort(df.payload_bytes.unique()).astype(float)
    c_uji = np.sort(df.concurrency.unique()).astype(float)
    tengah_b = np.sqrt(b_uji[:-1] * b_uji[1:])
    tengah_c = np.sqrt(c_uji[:-1] * c_uji[1:])
    baru = pd.DataFrame([(i, b, cc) for i in range(len(PROTO)) for b in tengah_b for cc in tengah_c],
                        columns=FITUR)
    baru["protocol"] = [PROTO[i] for i in baru.protocol_code]
    baru["estimasi_p50_ms"] = np.exp(akhir.predict(baru[FITUR])).round(1)
    tabel(baru, "tabel_4_13_estimasi", index=False)
    print(baru.to_string(index=False))

print("\nSelesai.")
