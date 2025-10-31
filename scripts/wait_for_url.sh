#!/usr/bin/env bash
URL=$1
TIMEOUT=${2:-30}
i=0
while [ $i -lt $TIMEOUT ]; do
  if curl -sS "$URL" >/dev/null 2>&1; then
    echo "ok"
    exit 0
  fi
  i=$((i+1))
  sleep 1
done
echo "timeout"
exit 1
