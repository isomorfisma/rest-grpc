#!/usr/bin/env bash
# Sertifikat TLS dengan SAN mengikuti alamat layanan di konfigurasi.
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/lib_config.sh

SAN="DNS:localhost,IP:127.0.0.1"
while read -r ip; do SAN="$SAN,IP:$ip"; done < <(q '.protocols[].ip')

openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
  -keyout server.key -out server.crt \
  -subj "/CN=localhost" -addext "subjectAltName=$SAN"
echo "Sertifikat dibuat untuk: $SAN"