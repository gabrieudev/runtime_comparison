#!/usr/bin/env bash
set -euo pipefail

# CONFIGURAÇÕES
CPUS="${CPUS:-1}"
MEM="${MEM:-1g}"
MEM_SWAP="${MEM_SWAP:-1g}"
REPS="${REPS:-2}"
VUS_LIST=(50 100 200)
DURATION="${DURATION:-1800s}"
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

# FUNÇÃO PARA MOSTRAR PROGRESSO DO K6
show_k6_progress() {
    local total="$1"
    local start
    start=$(date +%s)
    
    while true; do
        sleep 1
        now=$(date +%s)
        elapsed=$((now - start))
        
        if [ "$elapsed" -ge "$total" ]; then
            printf "\rK6 em execução: 100%% (%ds/%ds)\n" "$total" "$total"
            break
        fi
        
        percent=$((elapsed * 100 / total))
        printf "\rK6 em execução: %3d%% (%ds/%ds)" "$percent" "$elapsed" "$total"
    done
}

mkdir -p "$OUTDIR"

echo "Iniciando PostgreSQL..."
docker compose down -v 2>/dev/null || true
docker compose up -d postgres

# Aguardar PostgreSQL ficar pronto
echo "Aguardando PostgreSQL iniciar..."
for i in {1..60}; do
    if docker compose logs postgres 2>/dev/null | grep -q "database system is ready to accept connections"; then
        echo "✓ PostgreSQL está rodando"
        sleep 2
        break
    fi
    sleep 1
    echo -n "."
done

# Verificar se o banco foi inicializado
echo "Verificando inicialização do banco..."
if docker compose exec postgres psql -U postgres -d perfdb -c "SELECT COUNT(*) FROM products;" 2>/dev/null | grep -q "10000"; then
    echo "Banco de dados inicializado com 10000 produtos"
else
    echo "Falha na inicialização do banco. Tentando manualmente..."
    
    # Executar script de inicialização manualmente
    docker compose exec postgres psql -U postgres -d perfdb -f /docker-entrypoint-initdb.d/init.sql
    
    # Verificar novamente
    docker compose exec postgres psql -U postgres -d perfdb -c "SELECT COUNT(*) as total_products FROM products;"
fi

# BUILD
echo "Buildando imagens dos runtimes..."
docker build -f "$DOCKERFILE_NODE" -t "$IMG_NODE" .
docker build -f "$DOCKERFILE_BUN" -t "$IMG_BUN" .
docker build -f "$DOCKERFILE_DENO" -t "$IMG_DENO" .

# Aguardar containers ficarem prontos
wait_container() {
    local cname="$1"
    local port="$2"
    
    echo "Aguardando container $cname na porta $port..."
    for i in $(seq 1 30); do
        if curl -s -f "http://localhost:$port/ping" > /dev/null 2>&1; then
            echo "Container $cname está pronto (tentativa $i)"
            return 0
        fi
        sleep 1
    done
    
    echo "Container $cname não ficou pronto após 30 segundos"
    return 1
}

# EXPERIMENTO
for i in "${!runtimes[@]}"; do
    rt="${runtimes[$i]}"
    port="${ports[$i]}"
    img="IMG_${rt^^}"
    image="${!img}"
    
    echo ""
    echo "===== INICIANDO TESTES: runtime=$rt ====="
    
    for vus in "${VUS_LIST[@]}"; do
        for rep in $(seq 1 "$REPS"); do
            echo "--- runtime=$rt | vus=$vus | rep=$rep ---"
            
            DEST="$OUTDIR/$rt/vus_$vus/rep_$rep"
            mkdir -p "$DEST"
            
            cname="${rt}_test_${vus}_${rep}"
            
            # Limpar container anterior se existir
            docker rm -f "$cname" 2>/dev/null || true
            
            # Iniciar container da API
            echo "Iniciando container $cname..."
            docker run -d \
            --name "$cname" \
            --cpus="$CPUS" \
            --memory="$MEM" \
            --memory-swap="$MEM_SWAP" \
            -p "$port:3000" \
            --network "$(basename $(pwd))_perf_network" \
            "$image"
            
            # Aguardar container ficar pronto
            if ! wait_container "$cname" "$port"; then
                echo "Falha ao iniciar container $cname. Pulando teste..."
                docker logs "$cname" > "$DEST/container_startup.log" 2>&1 || true
                docker rm -f "$cname" >/dev/null
                continue
            fi
            
            sleep 3
            
            # Iniciar monitor
            echo "Iniciando monitoramento..."
            "$MONITOR_SCRIPT" "$cname" "$DEST/docker_stats.csv" 0.5 &
            MON_PID=$!
            
            # Iniciar container do k6
            echo "Executando teste de carga com K6 (VUs=$vus, Duration=$DURATION)..."
            
            # Testar se a API está respondendo antes de executar K6
            echo "Testando conexão com API..."
            if ! curl -s -f "http://localhost:$port/api/products" > /dev/null 2>&1; then
                echo "ERRO: API não está respondendo. Pulando teste K6."
                kill "$MON_PID" 2>/dev/null || true
                wait "$MON_PID" 2>/dev/null || true
                docker rm -f "$cname" >/dev/null
                continue
            fi
            
            # Executar K6
            echo "Iniciando K6: $vus VUs por $DURATION"
            
            DURATION_SECONDS="${DURATION%s}"
            
            docker run --rm \
            --network host \
            -v "$(pwd):/work" \
            -w /work \
            -e TARGET_URL="http://localhost:$port" \
            -e VUS="$vus" \
            -e DURATION="$DURATION" \
            "$K6_IMAGE" run \
            --vus "$vus" \
            --duration "$DURATION" \
            --summary-export "$DEST/k6_summary.json" \
            "$K6_SCRIPT" \
            > "$DEST/k6_stdout.log" 2>&1 &
            
            K6_PID=$!
            
            # Mostrar progresso enquanto o k6 roda
            show_k6_progress "$DURATION_SECONDS" &
            PROGRESS_PID=$!
            
            # Aguardar k6 terminar
            wait "$K6_PID" || true
            
            # Encerrar progresso
            kill "$PROGRESS_PID" 2>/dev/null || true
            wait "$PROGRESS_PID" 2>/dev/null || true
            
            echo "K6 finalizado!"
            
            sleep 2
            
            # Parar monitor
            echo "Parando monitoramento..."
            kill "$MON_PID" 2>/dev/null || true
            wait "$MON_PID" 2>/dev/null || true
            
            # Coletar logs
            echo "Coletando logs do container..."
            docker logs "$cname" > "$DEST/container.log" 2>&1 || true
            
            # Coletar estatísticas finais
            docker stats --no-stream "$cname" > "$DEST/docker_final_stats.log" 2>&1 || true
            
            # Parar e remover container
            docker rm -f "$cname" >/dev/null
            
            echo "Teste concluído. Resultados em: $DEST"
            echo ""
        done
    done
done

# LIMPEZA
echo "Parando PostgreSQL..."
docker compose down -v

echo ""
echo "========================================"
echo "Todos os experimentos finalizados."
echo "Resultados em: $OUTDIR"
