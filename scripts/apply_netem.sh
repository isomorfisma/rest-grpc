#!/usr/bin/env bash
# Menerapkan kondisi jaringan yang identik untuk kedua arah pada satu container.
# Dipanggil ulang setiap container dinyalakan, karena aturan pada eth0 hilang saat restart.
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/lib_config.sh

container=$1
BRIDGE=$(q '.network.bridge')
DELAY=$(q '.network.delay')
RATE=$(q '.network.rate')
LIMIT=$(q '.network.limit')

# Arah request (host → container): antrean keluar pada bridge
tc qdisc replace dev "$BRIDGE" root netem delay "$DELAY" rate "$RATE" limit "$LIMIT"

# Arah respons (container → host): antrean keluar eth0 di dalam namespace container
pid=$(docker inspect -f '{{.State.Pid}}' "$container")
nsenter -t "$pid" -n tc qdisc replace dev eth0 root netem delay "$DELAY" rate "$RATE" limit "$LIMIT"

echo "netem diterapkan pada $container dan $BRIDGE: delay=$DELAY rate=$RATE limit=$LIMIT"