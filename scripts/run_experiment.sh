#!/usr/bin/env bash
# Orkestrator eksperimen: blok bergantian per protokol, urutan acak, warm-up, repetisi.
# Seluruh parameter dibaca dari konfigurasi — tidak ada angka desain di berkas ini.
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/lib_config.sh

mapfile -t CLASSES < <(q '.payload_classes[].name')
mapfile -t CONCS   < <(q '.concurrency_levels[]')
mapfile -t PROTOS  < <(q '.protocols[].name')
REPS=$(q '.experiment.repetitions');   BATCH=$(q '.experiment.block_size')
WARMUP=$(q '.experiment.warmup');      DUR=$(q '.experiment.duration')
TIMEOUT=$(q '.experiment.timeout');    PAUSE=$(q '.experiment.pause_seconds')
SEED=$(q '.experiment.seed');          GEN_CPUS=$(q '.resources.generator_cpuset')
RAW=$(q '.output.raw_dir');            RUNLOG=$(q '.output.runlog')

for alat in /usr/bin/time openssl taskset jq k6; do
  command -v "$alat" >/dev/null || { echo "Tidak ditemukan: $alat" >&2; exit 1; }
done

# CPU (% dari satu vCPU) dan memori puncak pembangkit beban per run, untuk membuktikan generator bukan bottleneck
GENSTAT=$(mktemp -t genstat.XXXXXX)
trap 'rm -f "$CFG_FILE" "$GENSTAT"' EXIT

mkdir -p "$RAW" "$(dirname "$RUNLOG")"
[ -f "$RUNLOG" ] || echo "protocol,payload_class,concurrency,rep,block,start_ts,end_ts,gen_cpu_pct,gen_rss_mb" > "$RUNLOG"

# info <nama-protokol> <filter-jq> → satu nilai dari entri protokol tersebut
info () { jq -r --arg n "$1" '.protocols[] | select(.name==$n) | '"$2" "$CFG_FILE"; }

beban () {   # beban <protokol> <kelas> <conc> <durasi> <rep> [berkas-keluaran]
  # Kedua protokol diukur dengan k6 (k6/http dan k6/net/grpc): model beban, kebijakan koneksi,
  # dan skema keluaran identik. Skrip dipilih dari jenis protokol: loadtest/k6_<kind>.js
  local p=$1 s=$2 c=$3 d=$4 r=$5 out=${6:-}
  local kind ip port
  local ukur=()                                               # hanya run terukur yang dicatat
  [ -n "$out" ] && ukur=(/usr/bin/time -f '%e %U %S %M' -o "$GENSTAT")
  kind=$(info "$p" '.kind'); ip=$(info "$p" '.ip'); port=$(info "$p" '.port')

  local target="$ip:$port"
  [ "$kind" = rest ] && target="https://$ip:$port"
  "${ukur[@]}" taskset -c "$GEN_CPUS" k6 run --quiet "loadtest/k6_${kind}.js" \
    -e CFG_JSON="$CFG_FILE" -e PROTO="$p" -e TARGET="$target" \
    -e SIZE="$s" -e VUS="$c" -e DUR="$d" -e REP="$r" -e OUT="$out"
}

siap () {    # tunggu layanan menerima koneksi (maks. 60 detik)
  local p=$1 kind ip port
  kind=$(info "$p" '.kind'); ip=$(info "$p" '.ip'); port=$(info "$p" '.port')
  for _ in $(seq 60); do
    if [ "$kind" = rest ]; then
      curl -sfk "https://$ip:$port/healthz" >/dev/null && return
    else
      (exec 3<>"/dev/tcp/$ip/$port") 2>/dev/null && return
    fi
    sleep 1
  done
  echo "Layanan $p tidak siap" >&2; exit 1
}

docker compose up -d cadvisor prometheus
for p in "${PROTOS[@]}"; do docker compose stop "${p}-svc" 2>/dev/null || true; done

NB=$(( (REPS + BATCH - 1) / BATCH ))
for b in $(seq 1 "$NB"); do
  r0=$(( (b - 1) * BATCH + 1 )); r1=$(( b * BATCH < REPS ? b * BATCH : REPS ))
  if (( b % 2 )); then urutan=("${PROTOS[@]}"); else urutan=($(printf '%s\n' "${PROTOS[@]}" | tac)); fi

  for p in "${urutan[@]}"; do
    docker compose up -d "${p}-svc"
    siap "$p"
    scripts/apply_netem.sh "${p}-svc"

    daftar="data/order_$(basename "$RAW")_${p}_b${b}.txt"
    for s in "${CLASSES[@]}"; do for c in "${CONCS[@]}"; do for r in $(seq "$r0" "$r1"); do
      echo "$s $c $r"; done; done; done | shuf --random-source=<(openssl enc -aes-256-ctr -pbkdf2 -pass "pass:$SEED:$b" -nosalt </dev/zero 2>/dev/null) > "$daftar"

    while read -r s c r <&3; do
      out="$RAW/${p}_${s}_${c}_rep$(printf %02d "$r").json"
      [ -s "$out" ] && continue                                 # sudah ada → lewati
      beban "$p" "$s" "$c" "$WARMUP" "$r" >/dev/null || true     # warm-up, dibuang
      t0=$(date +%s)
      if beban "$p" "$s" "$c" "$DUR" "$r" "$out" >/dev/null; then
        t1=$(date +%s)
        read -r el us sy rss < <(tail -n1 "$GENSTAT")
        gcpu=$(awk -v e="$el" -v u="$us" -v k="$sy" 'BEGIN{printf "%.1f", (e > 0 ? 100*(u+k)/e : 0)}')
        echo "$p,$s,$c,$r,$b,$t0,$t1,$gcpu,$(( rss / 1024 ))" >> "$RUNLOG"
        printf '[%s] putaran %s  %s\n' "$(date +%T)" "$b" "$out"
      else
        echo "[$(date +%T)] GAGAL $out" >&2; rm -f "$out"
      fi
      sleep "$PAUSE"
    done 3< "$daftar"

    docker compose stop "${p}-svc"
  done
done

chown -R "${SUDO_USER:-$USER}" "$RAW" data
echo "Selesai: $(ls "$RAW" | wc -l) berkas di $RAW/"