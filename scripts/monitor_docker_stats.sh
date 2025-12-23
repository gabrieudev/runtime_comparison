#!/usr/bin/env bash
set -euo pipefail

CONTAINER="$1"
OUT_CSV="$2"
INTERVAL="${3:-1.0}"

if [[ -z "${CONTAINER:-}" || -z "${OUT_CSV:-}" ]]; then
    echo "Uso: $0 <container> <output_csv> [interval_seconds]" >&2
    exit 1
fi

# Cabeçalho do CSV
echo "timestamp,cpu_percent,mem_usage_mb,mem_limit_mb" > "$OUT_CSV"

container_exists() {
    docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"
}

to_mb() {
    local value="$1"
    local unit="$2"
    
    case "$unit" in
        KiB) awk "BEGIN {printf \"%.3f\", $value / 1024}" ;;
        MiB) awk "BEGIN {printf \"%.3f\", $value}" ;;
        GiB) awk "BEGIN {printf \"%.3f\", $value * 1024}" ;;
        B)   awk "BEGIN {printf \"%.6f\", $value / 1024 / 1024}" ;;
        kB)  awk "BEGIN {printf \"%.3f\", $value / 1024}" ;;
        MB)  awk "BEGIN {printf \"%.3f\", $value}" ;;
        GB)  awk "BEGIN {printf \"%.3f\", $value * 1024}" ;;
        *)   echo "" ;;
    esac
}

echo "Iniciando monitoramento do container: $CONTAINER" >&2

while true; do
    STATS=$(docker stats --no-stream \
        --format "{{.CPUPerc}}|{{.MemUsage}}" \
    "$CONTAINER" 2>/dev/null || true)
    
    if [[ -z "$STATS" ]]; then
        if container_exists; then
            sleep "$INTERVAL"
            continue
        else
            break
        fi
    fi
    
    CPU_RAW=$(echo "$STATS" | cut -d'|' -f1 | tr -d '%' | tr ',' '.')
    MEM_RAW=$(echo "$STATS" | cut -d'|' -f2)
    
    MEM_USED=$(echo "$MEM_RAW" | cut -d'/' -f1 | xargs)
    MEM_LIMIT=$(echo "$MEM_RAW" | cut -d'/' -f2 | xargs)
    
    parse_mem() {
        local raw="$1"
        [[ "$raw" =~ ^([0-9.]+)([A-Za-z]+)$ ]] || return
        to_mb "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}"
    }
    
    MEM_USED_MB=$(parse_mem "$MEM_USED" || echo "")
    MEM_LIMIT_MB=$(parse_mem "$MEM_LIMIT" || echo "")
    
    TIMESTAMP=$(date +%s.%N)
    
    echo "${TIMESTAMP},${CPU_RAW},${MEM_USED_MB},${MEM_LIMIT_MB}" >> "$OUT_CSV"
    
    sleep "$INTERVAL"
done

echo "Monitoramento finalizado para container $CONTAINER" >&2
