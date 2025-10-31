#!/usr/bin/env bash
set -euo pipefail

# Variáveis de ambiente
RESULTS_DIR=${RESULTS_DIR:-./results}
VUS_LIST=${VUS_LIST:-"100 500 1000"}
DURATION=${DURATION:-"30m"}
REPS=${REPS:-3}
BASE_PORT=${BASE_PORT:-3000}
K6_IMG=${K6_IMG:-loadimpact/k6:latest}

declare -A IMAGES=( ["node"]="tcc-node:latest" ["deno"]="tcc-deno:latest" ["bun"]="tcc-bun:latest" )
declare -A PORTS=( ["node"]=$BASE_PORT ["deno"]=$((BASE_PORT+1)) ["bun"]=$((BASE_PORT+2)) )

mkdir -p "$RESULTS_DIR"

echo "Construindo imagens (se necessário)..."
docker build -t tcc-node:latest ./runtimes/node
docker build -t tcc-deno:latest ./runtimes/deno
docker build -t tcc-bun:latest ./runtimes/bun

for runtime in node deno bun; do
  for vus in $VUS_LIST; do
    for rep in $(seq 1 $REPS); do
      echo "=== runtime=$runtime | vus=$vus | rep=$rep ==="
      port=${PORTS[$runtime]}
      img=${IMAGES[$runtime]}
      cname="tcc-${runtime}"

      # remove o container antigo (se existir)
      docker rm -f $cname >/dev/null 2>&1 || true

      # inicia o container
      echo "Iniciando container $cname a partir de $img na porta $port..."
      docker run --rm -d --name "$cname" -p ${port}:3000 -e PORT=3000 "$img"

      # espera o container ficar pronto
      echo "Aguardando o container se tornar pronto..."
      ./scripts/wait_for_url.sh "http://localhost:${port}/ping" 30
      if [ $? -ne 0 ]; then
        echo "O container não ficou pronto. Coletando logs:"
        docker logs $cname || true
        docker rm -f $cname || true
        exit 1
      fi

      # prepara o diretório de resultados
      outdir="${RESULTS_DIR}/${runtime}/vus_${vus}/rep_${rep}"
      mkdir -p "$outdir"

      # inicia o monitor (docker stats)
      monitor_file="${outdir}/monitor.csv"
      ./scripts/monitor_docker_stats.sh "$cname" "$monitor_file" 1 &
      MONITOR_PID=$!
      echo "PID do monitor: $MONITOR_PID"

      # inicia o k6 via imagem docker (escreve JSON no diretório de resultados)
      echo "Executando k6 (VUS=$vus, duração=$DURATION)..."
      docker run --rm -v "$(pwd)/k6:/scripts" -v "$(pwd)/${outdir}:/data" -e TARGET_URL="http://host.docker.internal:${port}" -e VUS="${vus}" -e DURATION="${DURATION}" $K6_IMG run /scripts/load.js --vus ${vus} --duration ${DURATION} --out json=/data/k6_${runtime}_vus${vus}_rep${rep}.json

      # para o monitor
      echo "Parando monitor..."
      kill $MONITOR_PID || true
      wait $MONITOR_PID 2>/dev/null || true

      # coleta logs do container
      docker logs "$cname" > "${outdir}/container.log" 2>&1 || true

      # para/remove o container
      docker rm -f "$cname" >/dev/null 2>&1 || true

      echo "Resultados salvos em ${outdir}"
      echo "Pausando 5s para a proxima execução..."
      sleep 5
    done
  done
done

echo "Todas as execu es conclu das. Resultados em ${RESULTS_DIR}."

