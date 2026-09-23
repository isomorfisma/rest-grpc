import sys

sys.path.insert(0, "scripts")
import cfg as C

c = C.load()
kelas, conc, proto = C.classes(c), c["concurrency_levels"], C.protocols(c)
e = c["experiment"]

sel = len(kelas) * len(conc) * len(proto)
run = sel * e["repetitions"]
per_run = C.seconds(e["warmup"]) + C.seconds(e["duration"]) + e["pause_seconds"] + 3
blok = -(-e["repetitions"] // e["block_size"]) * len(proto)

print(f"Kelas payload     : {len(kelas)} → {kelas}")
print(f"Level concurrency : {len(conc)} → {conc}")
print(f"Protokol          : {len(proto)} → {proto}")
print(f"Sel               : {sel}")
print(f"Repetisi per sel  : {e['repetitions']} → total {run} run")
print(f"Jumlah blok       : {blok} (ukuran blok {e['block_size']} repetisi)")
print(f"Durasi per run    : {per_run:.0f} s")
print(f"Perkiraan total   : {run * per_run / 3600:.1f} jam")
print(f"Keluaran          : {c['output']['raw_dir']}/ dan {c['output']['runlog']}")