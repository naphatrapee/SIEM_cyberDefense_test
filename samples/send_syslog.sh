#!/bin/bash
# Usage: ./send_syslog.sh [host] [port]   (UDP by default; add TCP with: nc host port)
HOST=${1:-localhost}; PORT=${2:-514}
while IFS= read -r line; do
  echo -n "$line" | nc -u -w1 "$HOST" "$PORT"
done < "$(dirname "$0")/sample_syslog.log"
echo "syslog sent to $HOST:$PORT"
