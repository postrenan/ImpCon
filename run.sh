#!/bin/bash
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Ambiente não encontrado. Execute primeiro: ./setup.sh"
  exit 1
fi

source .venv/bin/activate

mkdir -p logs
export IMPCON_LOGS="$(pwd)/logs"

echo "=== ImpCon iniciando em http://localhost:8500 ==="
echo "Pressione Ctrl+C para parar."
echo ""

uvicorn app:app --host 0.0.0.0 --port 8500 --reload
