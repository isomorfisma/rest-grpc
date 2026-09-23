#!/usr/bin/env bash
# Dipakai dengan: source scripts/lib_config.sh
# Menyiapkan $CFG_FILE (hasil gabungan) dan fungsi q untuk membaca nilai.
: "${CFG:=config/experiment.json}"
: "${OVERRIDE:=}"

CFG_FILE=$(mktemp -t cfg.XXXXXX.json)
trap 'rm -f "$CFG_FILE"' EXIT

if [ -n "$OVERRIDE" ]; then
  jq -s '.[0] * .[1]' "$CFG" "$OVERRIDE" > "$CFG_FILE"   # objek digabung, array ditimpa
else
  cp "$CFG" "$CFG_FILE"
fi

q () { jq -r "$1" "$CFG_FILE"; }     # contoh: q '.experiment.duration'