#!/usr/bin/env bash
set -euo pipefail

CONTAINER="$1"
OUT_CSV="$2"
INTERVAL="${3:-0.5}"

if [ -z "$CONTAINER" ] || [ -z "$OUT_CSV" ]; then
    echo "Uso: $0 <container> <output_csv> [interval_seconds]"
    exit 1
fi

# Cabeçalho CSV
echo "timestamp,cpu_percent,mem_usage_mb" > "$OUT_CSV"

# Função para converter memória para MB (docker stats pode retornar KiB/MiB/GiB)
to_mb() {
    local value="$1"
    local unit="$2"
    
    case "$unit" in
        KiB) awk "BEGIN { printf \"%.3f\", $value / 1024 }" ;;
        MiB) awk "BEGIN { printf \"%.3f\", $value }" ;;
        GiB) awk "BEGIN { printf \"%.3f\", $value * 1024 }" ;;
        *)   echo "0" ;;
    esac
}

while true; do
    # Formato: "cpu%|mem_used"
    STATS=$(docker stats --no-stream --format '{{.CPUPerc}}|{{.MemUsage}}' "$CONTAINER" 2>/dev/null || true)
    
    # Se o container não existir mais, encerra monitor
    if [ -z "$STATS" ]; then
        break
    fi
    
    CPU_RAW=$(echo "$STATS" | cut -d'|' -f1 | tr -d '%')
    MEM_RAW=$(echo "$STATS" | cut -d'|' -f2 | cut -d'/' -f1 | xargs)
    
    # MEM_RAW exemplo: "23.45MiB"
    MEM_VALUE=$(echo "$MEM_RAW" | sed -E 's/^([0-9.]+).*/\1/')
    MEM_UNIT=$(echo "$MEM_RAW" | sed -E 's/^[0-9.]+([A-Za-z]+).*/\1/')
    
    MEM_MB=$(to_mb "$MEM_VALUE" "$MEM_UNIT")
    
    TIMESTAMP=$(date +%s.%N)
    
    echo "${TIMESTAMP},${CPU_RAW},${MEM_MB}" >> "$OUT_CSV"
    
    sleep "$INTERVAL"
done
