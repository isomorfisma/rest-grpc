"""raw/*.json (k6 & ghz) + cpu.csv + payload_sizes.csv → data/dataset[_suffix].csv (1 baris per run)"""
import glob
import json
import os
import sys

import pandas as pd

sys.path.insert(0, "scripts")
import cfg

c = cfg.load()
SUF = cfg.suffix(c)                       # "" untuk eksperimen penuh, "_pilot" untuk pilot
RAW, DATA = c["output"]["raw_dir"], c["output"]["data_dir"]
records = {k["name"]: k.get("records") for k in c["payload_classes"]}
sizes = pd.read_csv(f"{DATA}/payload_sizes.csv").set_index("payload_class")


def dari_k6(j):
    return {k: j[k] for k in ("p50_ms", "p95_ms", "p99_ms", "mean_ms", "requests", "rps", "error_rate")}


def dari_ghz(j):
    lat = {d["percentage"]: d["latency"] / 1e6 for d in j["latencyDistribution"]}   # ns → ms
    n = j["count"]
    ok = j.get("statusCodeDistribution", {}).get("OK", 0)
    return {"p50_ms": lat[50], "p95_ms": lat[95], "p99_ms": lat[99],
            "mean_ms": j["average"] / 1e6, "requests": n, "rps": j["rps"],
            "error_rate": 1 - ok / n if n else 1.0}


rows = []
for path in sorted(glob.glob(f"{RAW}/*.json")):
    with open(path) as f:
        j = json.load(f)
    row = dari_k6(j) if j["tool"] == "k6" else dari_ghz(j)
    row.update(protocol=j["protocol"], payload_class=j["payload_class"],
               concurrency=int(j["concurrency"]), rep=int(j["rep"]))
    rows.append(row)

if not rows:
    sys.exit(f"Tidak ada berkas hasil di {RAW}/ — jalankan eksperimen lebih dulu.")

df = pd.DataFrame(rows)
df["records"] = df.payload_class.map(records)
df["payload_bytes"] = df.payload_class.map(sizes.json_bytes)
df["protobuf_bytes"] = df.payload_class.map(sizes.protobuf_bytes)

cpu_path = f"{DATA}/cpu{SUF}.csv"
if os.path.exists(cpu_path):
    cpu = pd.read_csv(cpu_path)
    gen = [k for k in ("gen_cpu_pct", "gen_rss_mb") if k in cpu.columns]   # runlog lama tidak punya kolom ini
    cpu = cpu[["protocol", "payload_class", "concurrency", "rep", "block", "cpu_percent"] + gen]
    df = df.merge(cpu, on=["protocol", "payload_class", "concurrency", "rep"], how="left")
else:
    print(f"PERINGATAN: {cpu_path} tidak ada; kolom CPU dan block dikosongkan. "
          "Jalankan collect_cpu.py lebih dulu bila metrik CPU diperlukan.", file=sys.stderr)
    df["block"] = pd.NA
    df["cpu_percent"] = pd.NA

df["throughput_rps"] = df.rps * (1 - df.error_rate)          # hanya permintaan yang berhasil
df["combo_id"] = df.protocol + "_" + df.payload_class + "_" + df.concurrency.astype(str)
df["protocol_code"] = pd.Categorical(df.protocol, categories=cfg.protocols(c)).codes
df["little_ratio"] = df.concurrency / (df.rps * df.mean_ms / 1000)   # ≈ 1 jika generator sehat

keluaran = f"{DATA}/dataset{SUF}.csv"
df.to_csv(keluaran, index=False)
print(len(df), "run ·", df.combo_id.nunique(), "sel →", keluaran)
print(df.groupby(["protocol", "concurrency"]).little_ratio.median().round(2))
if "gen_cpu_pct" in df:
    print("CPU pembangkit beban (maks, % dari satu vCPU):")
    print(df.groupby(["protocol", "concurrency"]).gen_cpu_pct.max().round(0))
