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

mkdir -p "$RAW" "$(dirname "$RUNLOG")"
[ -f "$RUNLOG" ] || echo "protocol,payload_class,concurrency,rep,block,start_ts,end_ts" > "$RUNLOG"

# info <nama-protokol> <filter-jq> → satu nilai dari entri protokol tersebut
info () { jq -r --arg n "$1" '.protocols[] | select(.name==$n) | '"$2" "$CFG_FILE"; }

beban () {   # beban <protokol> <kelas> <conc> <durasi> <rep> [berkas-keluaran]
  local p=$1 s=$2 c=$3 d=$4 r=$5 out=${6:-}
  local kind ip port call
  kind=$(info "$p" '.kind'); ip=$(info "$p" '.ip'); port=$(info "$p" '.port')

  if [ "$kind" = rest ]; then
    taskset -c "$GEN_CPUS" k6 run --quiet loadtest/k6_rest.js \
      -e CFG_JSON="$CFG_FILE" -e PROTO="$p" -e TARGET="https://$ip:$port" \
      -e SIZE="$s" -e VUS="$c" -e DUR="$d" -e REP="$r" -e OUT="$out"
  else
    call=$(info "$p" '.call')
    if [ -z "$out" ]; then       # warm-up: hasil dibuang
      taskset -c "$GEN_CPUS" ghz --skipTLS --proto payload.proto --call "$call" \
        -d "{\"size_class\":\"$s\"}" -c "$c" --connections 1 -z "$d" \
        --duration-stop=wait --timeout "$TIMEOUT" -O json "$ip:$port" > /dev/null
    else
      taskset -c "$GEN_CPUS" ghz --skipTLS --proto payload.proto --call "$call" \
        -d "{\"size_class\":\"$s\"}" -c "$c" --connections 1 -z "$d" \
        --duration-stop=wait --timeout "$TIMEOUT" -O json "$ip:$port" \
      | jq --arg p "$p" --arg s "$s" --argjson c "$c" --argjson r "$r" \
           'del(.details, .histogram)
            + {tool:"ghz", protocol:$p, payload_class:$s, concurrency:$c, rep:$r}' > "$out"
    fi
  fi
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
      echo "$s $c $r"; done; done; done | shuf --random-source=<(yes "$SEED$b") > "$daftar"

    while read -r s c r <&3; do
      out="$RAW/${p}_${s}_${c}_rep$(printf %02d "$r").json"
      [ -s "$out" ] && continue                                 # sudah ada → lewati
      beban "$p" "$s" "$c" "$WARMUP" "$r" >/dev/null || true     # warm-up, dibuang
      t0=$(date +%s)
      if beban "$p" "$s" "$c" "$DUR" "$r" "$out" >/dev/null; then
        echo "$p,$s,$c,$r,$b,$t0,$(date +%s)" >> "$RUNLOG"
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