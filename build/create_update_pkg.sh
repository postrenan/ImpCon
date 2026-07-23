#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

VERSION="${1:-1.1.0}"
CHANGELOG="${2:-Melhorias de desempenho e correções de bugs.}"
OUTPUT_DIR="${SCRIPT_DIR}/updates"
ZIP_NAME="ImpCon-Update-v${VERSION}.zip"
ZIP_PATH="${OUTPUT_DIR}/${ZIP_NAME}"

mkdir -p "$OUTPUT_DIR"
rm -f "$ZIP_PATH"

echo "Gerando pacote de atualização remota leve v${VERSION}..."
cd "$PROJECT_DIR"
zip -r -q "$ZIP_PATH" app.py modules/ static/ requirements.txt -x "*.pyc" -x "*__pycache__*"

SIZE=$(du -h "$ZIP_PATH" | cut -f1)

cat > "${OUTPUT_DIR}/version.json" << EOF
{
  "version": "${VERSION}",
  "download_url": "https://raw.githubusercontent.com/postrenan/ImpCon/main/build/updates/${ZIP_NAME}",
  "changelog": "${CHANGELOG}"
}
EOF

echo "✓ Pacote de atualização v${VERSION} criado com sucesso!"
echo "  Zip Pacote : ${ZIP_PATH} (${SIZE})"
echo "  Manifesto  : ${OUTPUT_DIR}/version.json"
