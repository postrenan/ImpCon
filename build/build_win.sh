#!/usr/bin/env bash
# =============================================================================
# ImpCon -- Gerador de pacote portável para Windows x64 (1-Clique .exe)
#
# Cria:  build/ImpCon-Windows-x64/
#   • ImpCon.exe           → Executável GUI nativo Windows (duplo clique e roda!)
#   • app.py & modules/    → Código da aplicação FastAPI
#   • static/              → Interface web frontend
#   • bin/python/          → Python 3.11 portátil para Windows com todas as libs
#   • bin/ollama.exe       → Executável do Ollama para Windows
#   • models/              → Modelo llama3.2:3b (~2 GB)
#   • fonts/               → Fontes DejaVu (para PDFs)
#   • start.bat            → Launcher via prompt de comando (alternativo)
#   • ImpCon.vbs           → Launcher silencioso via VBScript
#   • README.txt           → Instruções completas em português
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
OUT_NAME="ImpCon-Windows-x64"
OUT_DIR="$SCRIPT_DIR/$OUT_NAME"

MODEL="llama3.2:3b"
WINE_PY="/tmp/wine_py/python.exe"
TCC_EXE="/tmp/tcc/tcc/tcc.exe"
OLLAMA_WIN_URL="https://github.com/ollama/ollama/releases/latest/download/ollama-windows-amd64.zip"

GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
step() { echo -e "\n${BLUE}▶ [$1/7]${NC} $2"; }
ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC}  $1"; }
die()  { echo -e "${RED}ERRO:${NC} $1"; exit 1; }

echo -e "${GREEN}"
echo "  ╔═══════════════════════════════════════════════════════╗"
echo "  ║   ImpCon -- Build de Pacote Portável Windows (.exe)   ║"
echo "  ╚═══════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo "  Projeto : $PROJECT_DIR"
echo "  Saída   : $OUT_DIR"

# ── 1. Preparar pastas de saída ────────────────────────────────────────────────
step 1 "Preparando estrutura de diretórios do pacote..."
rm -rf "$OUT_DIR"
rm -f "$SCRIPT_DIR"/*.zip "$SCRIPT_DIR"/*.7z* "$SCRIPT_DIR"/*-whatsapp* 2>/dev/null || true
mkdir -p "$OUT_DIR"/{bin/python,models,fonts,temp,logs,static}
ok "Diretórios criados"

# ── 2. Compilar ImpCon.exe (1-Click Launcher) ─────────────────────────────────
step 2 "Compilando executável principal 'ImpCon.exe' (C WinMain)..."
if [ ! -f "$TCC_EXE" ]; then
    echo "  Baixando compilador C nativo..."
    mkdir -p /tmp/tcc
    curl -sSL -o /tmp/tcc/tcc.zip https://download.savannah.gnu.org/releases/tinycc/tcc-0.9.27-win64-bin.zip
    unzip -q -o /tmp/tcc/tcc.zip -d /tmp/tcc
fi

wine "$TCC_EXE" -mwindows -o "$OUT_DIR/ImpCon.exe" "$SCRIPT_DIR/launcher_win.c" -lshell32
ok "Executável nativo criado → $OUT_DIR/ImpCon.exe"

# ── 3. Preparar Python Portátil para Windows ──────────────────────────────────
step 3 "Montando ambiente Python 3.11 portátil para Windows com dependências..."
PY_ZIP="/tmp/python-3.11.9-embed-amd64.zip"
if [ ! -f "$PY_ZIP" ]; then
    curl -sSL -o "$PY_ZIP" https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip
fi

unzip -q -o "$PY_ZIP" -d "$OUT_DIR/bin/python"
cat > "$OUT_DIR/bin/python/python311._pth" << 'EOF'
python311.zip
.
Lib/site-packages
import site
EOF

# Copiar site-packages compilados para Windows
mkdir -p "$OUT_DIR/bin/python/Lib/site-packages"
if [ -d "/tmp/wine_py/Lib/site-packages" ]; then
    cp -r /tmp/wine_py/Lib/site-packages/* "$OUT_DIR/bin/python/Lib/site-packages/"
    ok "Dependências Python (FastAPI, Uvicorn, ReportLab, PdfPlumber, Matplotlib) integradas!"
else
    warn "site-packages não encontrado em /tmp/wine_py. Certifique-se de que os pacotes foram instalados."
fi

# ── 4. Copiar código do projeto ───────────────────────────────────────────────
step 4 "Copiando arquivos da aplicação ImpCon..."
cp "$PROJECT_DIR/app.py" "$OUT_DIR/"
cp -r "$PROJECT_DIR/modules" "$OUT_DIR/"
cp -r "$PROJECT_DIR/static"/* "$OUT_DIR/static/"
ok "Código fonte e frontend integrados"

# ── 5. Baixar/extrair Ollama Windows binary ────────────────────────────────────
step 5 "Baixando Ollama para Windows (ollama.exe)..."
OLLAMA_EXE="$OUT_DIR/bin/ollama.exe"

mkdir -p /tmp/ollama_win
if [ ! -f /tmp/ollama_win/ollama-windows-amd64.zip ]; then
    echo "  Baixando zip oficial do Ollama Windows..."
    curl -L --progress-bar -o /tmp/ollama_win/ollama-windows-amd64.zip "$OLLAMA_WIN_URL"
fi

rm -rf /tmp/ollama_win/extracted
unzip -q -o /tmp/ollama_win/ollama-windows-amd64.zip -d /tmp/ollama_win/extracted

EXTRACTED_EXE=$(find /tmp/ollama_win/extracted -name "ollama.exe" | head -n 1)
if [ -n "$EXTRACTED_EXE" ]; then
    cp "$EXTRACTED_EXE" "$OLLAMA_EXE"
    if [ -d "/tmp/ollama_win/extracted/lib" ]; then
        cp -r /tmp/ollama_win/extracted/lib "$OUT_DIR/"
        # Remover DLLs massivas de CUDA v12/v13 (1.7 GB) mantendo suporte CPU e Vulkan GPU (compatível com 100% de PCs)
        rm -rf "$OUT_DIR/lib/ollama/cuda_v12" "$OUT_DIR/lib/ollama/cuda_v13" 2>/dev/null || true
        ok "Bibliotecas otimizadas do Ollama (llama-server.exe + Vulkan + CPU) integradas em → $OUT_DIR/lib"
    fi
    ok "ollama.exe copiado → $OLLAMA_EXE"
else
    die "Não foi possível localizar ollama.exe no arquivo baixado."
fi

# ── 6. Copiar modelo de IA e fontes ────────────────────────────────────────────
step 6 "Integrando modelo llama3.2:3b e fontes DejaVu..."

SYSTEM_OLLAMA_DIRS=(
    "/usr/share/ollama/.ollama/models"
    "$HOME/.ollama/models"
    "/var/lib/ollama/models"
    "$SCRIPT_DIR/ImpCon-Linux-x64/models"
)

MODEL_PATH="$(echo "$MODEL" | sed 's|:|/|g')"

copy_model_from_system() {
    local SRC="$1"
    local MANIFEST_SRC="$SRC/manifests/registry.ollama.ai/library/${MODEL_PATH}"
    [ -f "$MANIFEST_SRC" ] || return 1

    echo "  Encontrado em $SRC -- copiando arquivos do modelo..."
    local MANIFEST_DST="$OUT_DIR/models/manifests/registry.ollama.ai/library/${MODEL_PATH}"
    mkdir -p "$(dirname "$MANIFEST_DST")"
    cp "$MANIFEST_SRC" "$MANIFEST_DST"

    local BLOBS_DST="$OUT_DIR/models/blobs"
    mkdir -p "$BLOBS_DST"
    python3 - "$MANIFEST_SRC" "$SRC/blobs" "$BLOBS_DST" << 'PYEOF'
import json, sys, shutil
from pathlib import Path
manifest_path, blobs_src, blobs_dst = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
with open(manifest_path) as f:
    manifest = json.load(f)
entries = manifest.get("layers", []) + [manifest.get("config", {})]
for e in entries:
    dig = e.get("digest", "")
    if not dig:
        continue
    fname = dig.replace(":", "-")
    src = blobs_src / fname
    dst = blobs_dst / fname
    if src.exists() and not dst.exists():
        print(f"  Copiando {fname[:30]}... ({src.stat().st_size // 1024**2} MB)")
        shutil.copy2(src, dst)
    elif dst.exists():
        print(f"  Já existe: {fname[:30]}")
PYEOF
    return 0
}

MODEL_READY=0
for SRC_DIR in "${SYSTEM_OLLAMA_DIRS[@]}"; do
    if copy_model_from_system "$SRC_DIR"; then
        MODEL_READY=1
        ok "Modelo llama3.2:3b copiado → $OUT_DIR/models/"
        break
    fi
done

if [ "$MODEL_READY" -eq 0 ]; then
    warn "Modelo local não encontrado em diretórios padrão. O usuário poderá baixar via Ollama se necessário."
fi

# Copiar fontes DejaVu
for d in /usr/share/fonts/truetype/dejavu /usr/share/fonts/dejavu /usr/share/fonts "$SCRIPT_DIR/ImpCon-Linux-x64/fonts"; do
    if ls "$d"/DejaVuSans*.ttf 2>/dev/null | grep -q .; then
        cp "$d"/DejaVuSans*.ttf "$OUT_DIR/fonts/" 2>/dev/null || true
        ok "Fontes DejaVu copiadas de $d"
        break
    fi
done

# ── 7. Launchers auxiliares e README ───────────────────────────────────────────
step 7 "Criando arquivos de atalho e README.txt..."

cat > "$OUT_DIR/ImpCon.vbs" << 'EOF'
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "ImpCon.exe", 0, False
EOF

cat > "$OUT_DIR/start.bat" << 'EOF'
@echo off
title ImpCon -- Analise Visual de Contratos
cd /d "%~dp0"

if exist "ImpCon.exe" (
    start "" "ImpCon.exe"
    exit /b
)

echo =======================================================
echo   ImpCon -- Analise Visual de Contratos
echo =======================================================
echo.

set OLLAMA_MODELS=%~dp0models
set OLLAMA_HOST=127.0.0.1:11435
set IMPCON_OLLAMA_URL=http://127.0.0.1:11435
set IMPCON_STATIC=%~dp0static
set IMPCON_TEMP=%~dp0temp
echo -^> Encerrando instancias anteriores se existirem...
taskkill /f /im ollama.exe /im python.exe >nul 2>&1

echo -^> Criando diretorios locais...
if not exist logs mkdir logs
if not exist temp mkdir temp

echo -^> Iniciando IA local (Ollama)...
start /b "" "%~dp0bin\ollama.exe" serve

echo -^> Aguardando servicos...
timeout /t 3 /nobreak >nul

echo -^> Abrindo navegador em http://localhost:8500 ...
start http://localhost:8500

echo -^> Servidor ImpCon iniciando...
set PYTHONPATH=%~dp0;%~dp0bin\python;%~dp0bin\python\Lib\site-packages
"%~dp0bin\python\python.exe" -m uvicorn app:app --host 0.0.0.0 --port 8500
EOF

cat > "$OUT_DIR/README.txt" << 'EOF'
ImpCon — Análise Visual de Contratos (Versão Windows Portável)
============================================================
Versão: 1.0 | Plataforma: Windows x64

COMO USAR (1-CLIQUE):
  1. Dê um duplo clique no arquivo `ImpCon.exe`
  2. O aplicativo iniciará a IA local e abrirá o navegador automaticamente em http://localhost:8500
  3. Arraste ou selecione um contrato (.pdf, .docx, .txt, .md)
  4. Aguarde a análise do contrato pela IA local
  5. Ajuste os diagramas gerados conforme necessário
  6. Clique em "Gerar PDF Final"

REQUISITOS DO SISTEMA:
  • Windows 10 ou Windows 11 (64-bit)
  • Mínimo 4 GB RAM (8 GB recomendado)
  • 100% Portável: Não exige instalação de Python, Ollama, Git ou dependências no sistema!

PRIVACIDADE E SEGURANÇA:
  • 100% Local -- Todo o processamento de contratos e IA ocorre dentro da sua própria máquina.
  • Sem envio de dados para servidores externos.
  • Funciona offline.

OBSERVAÇÕES E LOGS DE ERRO:
  • Se o Windows exibir um aviso do SmartScreen ("Fornecedor desconhecido"), clique em 
    "Mais informações" -> "Executar assim mesmo".
  • Caso ocorra qualquer erro durante o uso, consulte os arquivos na pasta `logs/`:
      - `logs/error.log`   : Erros detalhados e stack traces de exceções
      - `logs/impcon.log`  : Log de execução do aplicativo
      - `logs/ollama.log` : Log do servidor de IA local (Ollama)
      - `logs/server.log` : Log do servidor web FastAPI
EOF

ok "start.bat, ImpCon.vbs e README.txt gerados com sucesso"

# ── Finalização e empacotamento ────────────────────────────────────────────────
SIZE=$(du -sh "$OUT_DIR" 2>/dev/null | cut -f1)
echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗"
echo       "║   ✓ Build Windows (1-Click EXE) finalizado com sucesso!    ║"
echo -e    "╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "  Pacote   : $OUT_DIR"
echo "  Executável: $OUT_DIR/ImpCon.exe"
echo "  Tamanho  : $SIZE"
echo ""
echo -e "${BLUE}  Criando arquivos comprimidos 7-Zip (.7z) para distribuição (compatível com WhatsApp)...${NC}"
cd "$SCRIPT_DIR"
rm -f "$SCRIPT_DIR"/*.zip "$SCRIPT_DIR"/*.7z* "$SCRIPT_DIR"/*-whatsapp* 2>/dev/null || true
7z a -t7z -mx=1 "${OUT_NAME}.7z" "${OUT_NAME}/"
7z a -t7z -mx=1 -v500m "${OUT_NAME}-whatsapp.7z" "${OUT_NAME}/"
echo -e "${GREEN}  ✓ Arquivo 7z Único gerado: ${SCRIPT_DIR}/${OUT_NAME}.7z${NC}"
echo -e "${GREEN}  ✓ Arquivos 7z Divididos (WhatsApp 500MB): ${SCRIPT_DIR}/${OUT_NAME}-whatsapp.7z.001 ...${NC}"
echo ""
