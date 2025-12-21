#!/usr/bin/env bash
set -euo pipefail

# ---------------- CONFIG ----------------
CPUS="${CPUS:-2}"
MEM="${MEM:-2g}"
REPS="${REPS:-2}"
VUS_LIST=(10 50 100)
DURATION="${DURATION:-30s}"
OUTDIR="results"

K6_IMAGE="grafana/k6:latest"
MONITOR_SCRIPT="./scripts/monitor_docker_stats.sh"
K6_SCRIPT="./k6/load.js"

IMG_NODE="perf_node"
IMG_BUN="perf_bun"
IMG_DENO="perf_deno"

DOCKERFILE_NODE="./images/Dockerfile.node"
DOCKERFILE_BUN="./images/Dockerfile.bun"
DOCKERFILE_DENO="./images/Dockerfile.deno"

runtimes=(node bun deno)
ports=(3001 3002 3003)

mkdir -p "$OUTDIR"

# ---------------- BUILD ----------------
echo "Buildando imagens..."
docker build -f "$DOCKERFILE_NODE" -t "$IMG_NODE" .
docker build -f "$DOCKERFILE_BUN" -t "$IMG_BUN" .
docker build -f "$DOCKERFILE_DENO" -t "$IMG_DENO" .

# ---------------- HELPERS ----------------
wait_container() {
    local cname="$1"
    for _ in {1..30}; do
        status=$(docker inspect -f '{{.State.Health.Status}}' "$cname" 2>/dev/null || echo "")
        if [ -z "$status" ] || [ "$status" = "healthy" ]; then
            return 0
        fi
        sleep 1
    done
    echo "Container $cname não ficou healthy"
}

# ---------------- EXPERIMENTOS ----------------
for i in "${!runtimes[@]}"; do
    rt="${runtimes[$i]}"
    port="${ports[$i]}"
    img="IMG_${rt^^}"
    image="${!img}"
    
    echo ""
    echo "===== INICIANDO TESTES: runtime=$rt ====="
    
    for vus in "${VUS_LIST[@]}"; do
        for rep in $(seq 1 "$REPS"); do
            echo "runtime=$rt | vus=$vus | rep=$rep"
            
            DEST="$OUTDIR/$rt/vus_$vus/rep_$rep"
            mkdir -p "$DEST"
            
            cname="${rt}_test_${vus}_${rep}"
            
            # --- Iniciar container da API ---
            docker run -d \
            --name "$cname" \
            --cpus="$CPUS" \
            --memory="$MEM" \
            -p "$port:3000" \
            "$image"
            
            wait_container "$cname"
            sleep 1
            
            # --- Iniciar monitor ---
            "$MONITOR_SCRIPT" "$cname" "$DEST/docker_stats.csv" 0.5 &
            MON_PID=$!
            
            # --- Iniciar container do k6 ---
            echo "Executando k6 (container)..."
            docker run --rm \
            --network host \
            -v "$(pwd):/work" \
            -w /work \
            "$K6_IMAGE" run \
            --vus "$vus" \
            --duration "$DURATION" \
            --env TARGET_URL="http://localhost:$port" \
            --out json="$DEST/k6_results.json" \
            "$K6_SCRIPT" > "$DEST/k6_stdout.log" 2>&1 || true
            
            sleep 1
            kill "$MON_PID" || true
            
            docker logs "$cname" > "$DEST/container.log" 2>&1 || true
            docker rm -f "$cname" >/dev/null
            
            echo "Resultados em $DEST"
        done
    done
done

echo ""
echo "Todos os experimentos finalizados."
echo "Resultados em: $OUTDIR"
