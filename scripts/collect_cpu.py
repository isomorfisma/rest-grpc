"""CPU container pada jendela waktu setiap run (runlog) → data/cpu[_suffix].csv"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

import pandas as pd

sys.path.insert(0, "scripts")
import cfg

c = cfg.load()
SUF = cfg.suffix(c)                       # "" untuk eksperimen penuh, "_pilot" untuk pilot
DATA = c["output"]["data_dir"]
PROM = c["monitoring"]["prometheus_url"] + "/api/v1/query"
KELUARAN = f"{DATA}/cpu{SUF}.csv"


def cpu_percent(container, end_ts, window_s):
    # detik-CPU terpakai selama jendela ÷ lama jendela × 100 = persen dari satu core
    if window_s <= 0:
        return None
    q = f'sum(increase(container_cpu_usage_seconds_total{{name="{container}"}}[{window_s}s]))'
    url = PROM + "?" + urllib.parse.urlencode({"query": q, "time": end_ts})
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            hasil = json.load(r)["data"]["result"]
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"  gagal menghubungi Prometheus: {e}", file=sys.stderr)
        return None
    return 100.0 * float(hasil[0]["value"][1]) / window_s if hasil else None


log = pd.read_csv(c["output"]["runlog"])
log["cpu_percent"] = [
    cpu_percent(f"{p}-svc", int(end), int(end - start))
    for p, start, end in zip(log.protocol, log.start_ts, log.end_ts)
]
log.to_csv(KELUARAN, index=False)

kosong = int(log.cpu_percent.isna().sum())
print(f"{len(log)} run → {KELUARAN}")
if kosong:
    print(f"PERINGATAN: {kosong} run tanpa data CPU. Periksa nama container, "
          "status target Prometheus, dan retensi TSDB.", file=sys.stderr)
print(log.groupby(["protocol", "concurrency"]).cpu_percent.describe().round(1))
