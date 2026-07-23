import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

_APP_ROOT = Path(__file__).resolve().parent
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from modules.diagrams import generate_diagrams
from modules.extractor import extract_contract_data
from modules.extractor import OLLAMA_HOST  # used by /api/models health check
from modules.pdf_builder import build_pdf
from modules.reader import read_document
from modules.updater import check_for_updates, apply_update, CURRENT_VERSION

import logging
from logging.handlers import RotatingFileHandler

STATIC_DIR = os.environ.get("IMPCON_STATIC", "static")
TEMP_DIR   = Path(os.environ.get("IMPCON_TEMP", "temp"))
TEMP_DIR.mkdir(parents=True, exist_ok=True)

LOGS_DIR   = Path(os.environ.get("IMPCON_LOGS", "logs"))
LOGS_DIR.mkdir(parents=True, exist_ok=True)

log_formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s")

file_handler = RotatingFileHandler(
    LOGS_DIR / "impcon.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)

error_file_handler = RotatingFileHandler(
    LOGS_DIR / "error.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
error_file_handler.setFormatter(log_formatter)
error_file_handler.setLevel(logging.ERROR)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.INFO)

logger = logging.getLogger("impcon")
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(error_file_handler)
logger.addHandler(console_handler)

ALLOWED_EXTENSIONS = {".docx", ".pdf", ".txt", ".md"}
MAX_FILE_MB = 20

DIAGRAM_LABELS: dict[str, str] = {
    "parties":     "Relacionamento entre Partes",
    "timeline":    "Linha do Tempo",
    "values":      "Valores Financeiros",
    "obligations": "Fluxo de Obrigações",
    "penalties":   "Mapa de Penalidades",
}

app = FastAPI(title="ImpCon — Análise Visual de Contratos")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

sessions: dict[str, dict] = {}


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return FileResponse("static/index.html")


class ApplyUpdateRequest(BaseModel):
    download_url: str


@app.get("/api/update/check")
async def check_update_endpoint():
    return await check_for_updates()


@app.post("/api/update/apply")
async def apply_update_endpoint(req: ApplyUpdateRequest):
    return await apply_update(req.download_url, _APP_ROOT)


@app.get("/api/models")
async def list_models():
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_HOST}/api/tags")
            data = resp.json()
            models = [m["name"] for m in data.get("models", [])]
            return {"models": models, "ok": True}
    except Exception:
        return {"models": [], "ok": False, "error": "Ollama não encontrado em localhost:11434"}


@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    model: str = Form("llama3.2:3b"),
    diagram_config: str = Form("{}"),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            400,
            f"Formato não suportado: '{ext}'. Aceitos: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    if len(content) > MAX_FILE_MB * 1024 * 1024:
        raise HTTPException(400, f"Arquivo muito grande. Limite: {MAX_FILE_MB} MB")

    try:
        config = json.loads(diagram_config)
    except json.JSONDecodeError:
        config = {}

    session_id = str(uuid.uuid4())
    session_dir = TEMP_DIR / session_id
    session_dir.mkdir()

    safe_name = Path(file.filename).name
    file_path = session_dir / safe_name
    file_path.write_bytes(content)

    sessions[session_id] = {
        "file": str(file_path),
        "model": model,
        "diagram_config": config,
        "status": "uploaded",
    }

    return {"session_id": session_id}


# ── Stage 1: read → extract → generate diagrams → return preview ───────────────

@app.get("/api/process/{session_id}")
async def process_document(session_id: str):
    if session_id not in sessions:
        raise HTTPException(404, "Sessão não encontrada")

    async def stream():
        session = sessions[session_id]

        def event(kind: str, **kwargs) -> str:
            return f"data: {json.dumps({'type': kind, **kwargs})}\n\n"

        try:
            # Step 1 — read
            yield event("progress", step="reading", message="Lendo documento…")
            await asyncio.sleep(0)
            text = read_document(session["file"])

            if not text.strip():
                yield event("error", message="Não foi possível extrair texto do documento.")
                return

            yield event("progress", step="reading",
                        message=f"Documento lido ({len(text):,} caracteres).")

            # Step 2 — LLM extraction
            yield event("progress", step="extracting",
                        message=f"Extraindo dados com IA local ({session['model']})…")
            await asyncio.sleep(0)

            data = await extract_contract_data(text, session["model"])

            has_data = any([
                data.get("partes"), data.get("datas"), data.get("valores"),
                data.get("obrigacoes"), data.get("clausulas_principais"),
            ])
            if not has_data:
                yield event("progress", step="extracting",
                            message="⚠ Extração parcial — continuando com o que foi encontrado.")
            else:
                yield event("progress", step="extracting",
                            message=(
                                f"Extraídos: {len(data.get('partes',[]))} partes · "
                                f"{len(data.get('datas',[]))} datas · "
                                f"{len(data.get('valores',[]))} valores · "
                                f"{len(data.get('obrigacoes',[]))} obrigações."
                            ))

            # Step 3 — generate diagrams
            cfg = session.get("diagram_config", {})
            enabled = [k for k, v in cfg.items() if v.get("enabled")]
            label = ", ".join(enabled) if enabled else "todos"
            yield event("progress", step="diagrams", message=f"Gerando diagramas: {label}…")
            await asyncio.sleep(0)

            diagram_paths = generate_diagrams(data, session_id, TEMP_DIR, cfg)
            n = len(diagram_paths)

            sessions[session_id]["diagram_paths"] = diagram_paths
            sessions[session_id]["extracted_data"] = data
            sessions[session_id]["text"] = text
            sessions[session_id]["status"] = "ready_to_build"

            yield event("progress", step="diagrams",
                        message=f"{n} diagrama(s) gerado(s).")

            # Build preview list for frontend
            previews = []
            for key, path in diagram_paths.items():
                previews.append({
                    "key":      key,
                    "label":    DIAGRAM_LABELS.get(key, key.capitalize()),
                    "url":      f"/api/diagram/{session_id}/{key}",
                    "included": True,
                })

            yield event("preview",
                        data=data,
                        diagrams=previews)

        except Exception as exc:
            logger.exception(f"Erro no processamento da sessão '{session_id}': {exc}")
            yield event("error", message=str(exc))

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Serve individual diagram preview images ────────────────────────────────────

@app.get("/api/diagram/{session_id}/{key}")
async def get_diagram(session_id: str, key: str):
    if session_id not in sessions:
        raise HTTPException(404, "Sessão não encontrada")

    paths = sessions[session_id].get("diagram_paths", {})
    path = paths.get(key)
    if not path or not Path(path).exists():
        raise HTTPException(404, "Diagrama não encontrado")

    return FileResponse(path, media_type="image/png")


# ── Stage 2: build PDF with selected diagrams ──────────────────────────────────

class BuildRequest(BaseModel):
    excluded: list[str] = []


@app.post("/api/build/{session_id}")
async def build_pdf_endpoint(session_id: str, req: BuildRequest):
    if session_id not in sessions:
        raise HTTPException(404, "Sessão não encontrada")

    session = sessions[session_id]
    if session.get("status") != "ready_to_build":
        raise HTTPException(400, "Sessão não está pronta para gerar PDF. Execute /api/process primeiro.")

    async def stream():
        def event(kind: str, **kwargs) -> str:
            return f"data: {json.dumps({'type': kind, **kwargs})}\n\n"

        try:
            yield event("progress", step="pdf", message="Montando PDF visual…")
            await asyncio.sleep(0)

            all_paths = session.get("diagram_paths", {})
            selected_paths = {k: v for k, v in all_paths.items() if k not in req.excluded}

            excluded_count = len(req.excluded)
            if excluded_count:
                yield event("progress", step="pdf",
                            message=f"Usando {len(selected_paths)} diagrama(s) ({excluded_count} removido(s) por você).")

            pdf_path = build_pdf(
                session["text"],
                session["extracted_data"],
                selected_paths,
                session_id,
                TEMP_DIR,
            )
            sessions[session_id]["pdf_path"] = str(pdf_path)
            sessions[session_id]["status"] = "done"

            yield event("complete",
                        pdf_url=f"/api/download/{session_id}",
                        data=session["extracted_data"],
                        diagrams=list(selected_paths.keys()))

        except Exception as exc:
            import traceback
            traceback.print_exc()
            yield event("error", message=str(exc))

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Download ───────────────────────────────────────────────────────────────────

@app.get("/api/download/{session_id}")
async def download_pdf(session_id: str):
    if session_id not in sessions:
        raise HTTPException(404, "Sessão não encontrada")

    pdf_path = sessions[session_id].get("pdf_path")
    if not pdf_path or not Path(pdf_path).exists():
        raise HTTPException(404, "PDF ainda não gerado")

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename="contrato_visual.pdf",
    )
