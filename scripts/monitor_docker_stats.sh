#!/usr/bin/env bash
CONTAINER=$1
OUT=$2
INTERVAL=${3:-1}

echo "timestamp,cpu_percent,mem_usage,mem_limit,mem_percent,net_io,block_io,pids" > "$OUT"

while true; do
  if [ -z "$(docker ps --filter "name=$CONTAINER" --format '{{.Names}}')" ]; then
    # container não existe
    echo "$(date +%s),0,0,0,0,0,0,0" >> "$OUT"
    sleep $INTERVAL
    continue
  fi

  line=$(docker stats --no-stream --format "{{.CPUPerc}},{{.MemUsage}},{{.MemPerc}},{{.NetIO}},{{.BlockIO}},{{.PIDs}}" "$CONTAINER" 2>/dev/null)
  if [ -z "$line" ]; then
    echo "$(date +%s),0,0,0,0,0,0,0" >> "$OUT"
  else
    cpu=$(echo "$line" | awk -F',' '{print $1}')
    memUsage=$(echo "$line" | awk -F',' '{print $2}')
    memPerc=$(echo "$line" | awk -F',' '{print $3}')
    netio=$(echo "$line" | awk -F',' '{print $4}')
    blockio=$(echo "$line" | awk -F',' '{print $5}')
    pids=$(echo "$line" | awk -F',' '{print $6}')
    echo "$(date +%s),${cpu},\"${memUsage}\",,${memPerc},\"${netio}\",\"${blockio}\",${pids}" >> "$OUT"
  fi

  sleep $INTERVAL
done
