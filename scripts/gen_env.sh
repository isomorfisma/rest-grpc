#!/usr/bin/env bash
# docker compose tidak bisa membaca JSON, jadi konfigurasi diterjemahkan ke .env.
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/lib_config.sh

{
  echo "# DIBUAT OTOMATIS oleh scripts/gen_env.sh — jangan diedit manual"
  echo "SUBNET=$(q '.network.subnet')"
  echo "BRIDGE=$(q '.network.bridge')"
  echo "CPUS=$(q '.resources.cpus')"
  echo "MEMORY=$(q '.resources.memory')"
  echo "SERVICE_CPUSET=$(q '.resources.service_cpuset')"
  echo "MONITOR_CPUSET=$(q '.resources.generator_cpuset')"
  echo "GOMEMLIMIT=$(q '.resources.gomemlimit')"
  jq -r '.protocols[] | "\(.name | ascii_upcase)_IP=\(.ip)\n\(.name | ascii_upcase)_PORT=\(.port)"' "$CFG_FILE"
} > .env
cat .env